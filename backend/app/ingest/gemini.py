import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Group, UsageFact, User
from app.ingest.common import decimal_from_json_number, labels_to_dict, stable_key, usage_date_from_bigquery


GEMINI_PLATFORM = "gemini"


@dataclass
class GeminiAccumulator:
    usage_start_time: str
    usage_end_time: str
    project_id: str
    owner: str
    model: str
    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost_usd: Decimal = Decimal("0")
    output_cost_usd: Decimal = Decimal("0")


def _sku_direction(description: str) -> str:
    if "Input Tokens" in description:
        return "input"
    if "Output Tokens" in description:
        return "output"
    raise ValueError(f"Unsupported Gemini SKU description: {description}")


def _gemini_dimensions(row: dict[str, Any], labels: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row["usage_start_time"],
        row["usage_end_time"],
        row["project"]["id"],
        labels["owner"],
        labels["model"],
        labels["agent"],
    )


def ingest_gemini(session: Session, starter_kit: Path) -> None:
    gemini_files = sorted((starter_kit / "data" / "gemini").glob("*.jsonl"))
    if len(gemini_files) != 1:
        raise ValueError(f"Expected one Gemini JSONL file, found {len(gemini_files)}")

    groups_by_project = {group.gcp_project_id: group for group in session.scalars(select(Group)).all()}
    users_by_email = {user.email: user for user in session.scalars(select(User)).all()}

    accumulators: dict[tuple[str, str, str, str, str, str], GeminiAccumulator] = {}

    with gemini_files[0].open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            labels = labels_to_dict(row["labels"])
            project_labels = labels_to_dict(row["project"]["labels"])

            group = groups_by_project.get(row["project"]["id"])
            if group is None:
                raise ValueError(f"Gemini row references unknown project {row['project']['id']}")
            if project_labels.get("team") != group.group_id:
                raise ValueError(
                    f"Gemini project team label {project_labels.get('team')} does not match group {group.group_id}"
                )
            if project_labels.get("cost-centre", "").upper() != group.cost_centre:
                raise ValueError(f"Gemini project cost-centre does not match group {group.group_id}")

            user = users_by_email.get(labels["owner"])
            if user is None:
                raise ValueError(f"Gemini row references unknown owner {labels['owner']}")
            if user.primary_group_id != group.group_id:
                raise ValueError(f"Gemini owner {user.email} is not in project group {group.group_id}")

            key = _gemini_dimensions(row, labels)
            acc = accumulators.get(key)
            if acc is None:
                acc = GeminiAccumulator(
                    usage_start_time=row["usage_start_time"],
                    usage_end_time=row["usage_end_time"],
                    project_id=row["project"]["id"],
                    owner=labels["owner"],
                    model=labels["model"],
                    agent=labels["agent"],
                )
                accumulators[key] = acc

            tokens = int(row["usage"]["amount"])
            cost = decimal_from_json_number(row["cost"])
            direction = _sku_direction(row["sku"]["description"])
            if direction == "input":
                acc.input_tokens += tokens
                acc.input_cost_usd += cost
            else:
                acc.output_tokens += tokens
                acc.output_cost_usd += cost

    for key, acc in accumulators.items():
        group = groups_by_project[acc.project_id]
        user = users_by_email[acc.owner]
        source_key = stable_key(list(key))
        total_tokens = acc.input_tokens + acc.output_tokens
        total_cost = acc.input_cost_usd + acc.output_cost_usd

        fact = session.scalar(
            select(UsageFact).where(
                UsageFact.platform == GEMINI_PLATFORM,
                UsageFact.source_key == source_key,
            )
        ) or UsageFact(platform=GEMINI_PLATFORM, source_key=source_key)

        fact.usage_date = usage_date_from_bigquery(acc.usage_start_time)
        fact.user_id = user.user_id
        fact.group_id = group.group_id
        fact.model = acc.model
        fact.product = None
        fact.source_dimension = acc.agent
        fact.uncached_input_tokens = acc.input_tokens
        fact.cache_read_input_tokens = 0
        fact.cache_creation_5m_input_tokens = 0
        fact.cache_creation_1h_input_tokens = 0
        fact.input_tokens = acc.input_tokens
        fact.output_tokens = acc.output_tokens
        fact.total_tokens = total_tokens
        fact.source_total_tokens = None
        fact.requests = None
        fact.web_search_requests = 0
        fact.token_cost_usd = Decimal("0")
        fact.web_search_cost_usd = Decimal("0")
        fact.input_cost_usd = acc.input_cost_usd
        fact.output_cost_usd = acc.output_cost_usd
        fact.cost_usd = total_cost
        session.add(fact)
