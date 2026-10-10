import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Group, UsageFact, User
from app.ingest.common import cents_to_usd, stable_key, usage_date_from_rfc3339


CLAUDE_PLATFORM = "claude"


def _claude_dimensions(row: dict[str, Any]) -> list[str]:
    return [
        row["actor"]["user_id"],
        row["actor"]["email"],
        row["starting_at"],
        row["ending_at"],
        row["rbac_group_id"],
        row["product"],
        row["model"],
        row["context_window"],
        row["speed"],
        row["inference_geo"],
    ]


def _cost_index(cost_rows: list[dict[str, Any]]) -> dict[str, dict[str, Decimal]]:
    indexed: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in cost_rows:
        if row["cost_type"] not in {"tokens", "web_search"}:
            raise ValueError(f"Unsupported Claude cost_type: {row['cost_type']}")
        key = stable_key(_claude_dimensions(row))
        indexed[key][row["cost_type"]] = cents_to_usd(row["amount"])
    return indexed


def ingest_claude(session: Session, starter_kit: Path) -> None:
    usage_path = starter_kit / "data" / "claude" / "user_usage_report.json"
    cost_path = starter_kit / "data" / "claude" / "user_cost_report.json"

    usage_rows = json.loads(usage_path.read_text(encoding="utf-8"))["data"]
    cost_rows = json.loads(cost_path.read_text(encoding="utf-8"))["data"]
    costs = _cost_index(cost_rows)
    matched_cost_keys: set[str] = set()

    groups_by_rbac = {
        group.claude_rbac_group_id: group
        for group in session.scalars(select(Group)).all()
    }
    users_by_id = {user.user_id: user for user in session.scalars(select(User)).all()}

    for row in usage_rows:
        source_key = stable_key(_claude_dimensions(row))
        user = users_by_id.get(row["actor"]["user_id"])
        if user is None or user.email != row["actor"]["email"]:
            raise ValueError(f"Claude row references unknown or mismatched user {row['actor']}")

        group = groups_by_rbac.get(row["rbac_group_id"])
        if group is None:
            raise ValueError(f"Claude row references unknown RBAC group {row['rbac_group_id']}")
        if user.primary_group_id != group.group_id:
            raise ValueError(f"Claude user {user.user_id} is not in RBAC group {group.group_id}")

        cache_creation = row["cache_creation"]
        input_tokens = (
            row["uncached_input_tokens"]
            + row["cache_read_input_tokens"]
            + cache_creation["ephemeral_5m_input_tokens"]
            + cache_creation["ephemeral_1h_input_tokens"]
        )
        expected_total = input_tokens + row["output_tokens"]
        if expected_total != row["total_tokens"]:
            raise ValueError(
                f"Claude total token mismatch for {source_key}: source={row['total_tokens']} calculated={expected_total}"
            )

        row_costs = costs.get(source_key, {})
        if row_costs:
            matched_cost_keys.add(source_key)
        token_cost = row_costs.get("tokens", Decimal("0"))
        web_search_cost = row_costs.get("web_search", Decimal("0"))
        total_cost = token_cost + web_search_cost

        fact = session.scalar(
            select(UsageFact).where(
                UsageFact.platform == CLAUDE_PLATFORM,
                UsageFact.source_key == source_key,
            )
        ) or UsageFact(platform=CLAUDE_PLATFORM, source_key=source_key)

        fact.usage_date = usage_date_from_rfc3339(row["starting_at"])
        fact.user_id = user.user_id
        fact.group_id = group.group_id
        fact.model = row["model"]
        fact.product = row["product"]
        fact.source_dimension = row["product"]
        fact.uncached_input_tokens = row["uncached_input_tokens"]
        fact.cache_read_input_tokens = row["cache_read_input_tokens"]
        fact.cache_creation_5m_input_tokens = cache_creation["ephemeral_5m_input_tokens"]
        fact.cache_creation_1h_input_tokens = cache_creation["ephemeral_1h_input_tokens"]
        fact.input_tokens = input_tokens
        fact.output_tokens = row["output_tokens"]
        fact.total_tokens = row["total_tokens"]
        fact.source_total_tokens = row["total_tokens"]
        fact.requests = row["requests"]
        fact.web_search_requests = row["server_tool_use"]["web_search_requests"]
        fact.token_cost_usd = token_cost
        fact.web_search_cost_usd = web_search_cost
        fact.input_cost_usd = Decimal("0")
        fact.output_cost_usd = Decimal("0")
        fact.cost_usd = total_cost
        session.add(fact)

    unmatched_cost_keys = set(costs) - matched_cost_keys
    if unmatched_cost_keys:
        raise ValueError(f"Claude cost rows without matching usage rows: {len(unmatched_cost_keys)}")
