import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.domain.models import Group, UsageFact, User
from app.ingest.claude import ingest_claude
from app.ingest.common import cents_to_usd, labels_to_dict, stable_key
from app.ingest.directory import load_directory
from app.ingest.gemini import ingest_gemini
from app.ingest.loader import ingest_all

STARTER_KIT = Path(__file__).resolve().parents[2] / "starter-kit"


def _claude_usage_rows():
    return json.loads((STARTER_KIT / "data" / "claude" / "user_usage_report.json").read_text())["data"]


def _claude_cost_rows():
    return json.loads((STARTER_KIT / "data" / "claude" / "user_cost_report.json").read_text())["data"]


def _claude_key(row):
    return stable_key(
        [
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
    )


def _gemini_rows():
    path = next((STARTER_KIT / "data" / "gemini").glob("*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


def _gemini_key(row):
    labels = labels_to_dict(row["labels"])
    return stable_key(
        [
            row["usage_start_time"],
            row["usage_end_time"],
            row["project"]["id"],
            labels["owner"],
            labels["model"],
            labels["agent"],
        ]
    )


def _platform_totals(session):
    return {
        platform: {
            "total_tokens": session.scalar(
                select(func.sum(UsageFact.total_tokens)).where(UsageFact.platform == platform)
            ),
            "cost_usd": session.scalar(select(func.sum(UsageFact.cost_usd)).where(UsageFact.platform == platform)),
        }
        for platform in ("claude", "gemini")
    }


def test_directory_attribution(ingested_session):
    users = ingested_session.scalars(select(User)).all()
    groups = ingested_session.scalars(select(Group)).all()

    assert len(users) == 22
    assert len(groups) == 6
    assert ingested_session.get(User, "user_E7691888F28227066DD2FB86").primary_group_id == "clinical-operations"
    assert (
        ingested_session.get(Group, "clinical-operations").claude_rbac_group_id
        == "rbac_group_33DEEC83113481C9BD69498282"
    )


def test_claude_group_attribution_through_rbac_group_id(ingested_session):
    source = _claude_usage_rows()[0]
    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "claude", UsageFact.source_key == _claude_key(source))
    )

    assert fact.group_id == "clinical-operations"
    assert fact.user_id == source["actor"]["user_id"]


def test_claude_input_token_calculation_and_source_total_reconciliation(ingested_session):
    source = _claude_usage_rows()[0]
    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "claude", UsageFact.source_key == _claude_key(source))
    )
    cache_creation = source["cache_creation"]
    expected_input = (
        source["uncached_input_tokens"]
        + source["cache_read_input_tokens"]
        + cache_creation["ephemeral_5m_input_tokens"]
        + cache_creation["ephemeral_1h_input_tokens"]
    )

    assert fact.input_tokens == expected_input
    assert fact.source_total_tokens == source["total_tokens"]
    assert fact.total_tokens == fact.input_tokens + fact.output_tokens
    assert fact.total_tokens == source["total_tokens"]


def test_claude_cents_to_usd_conversion():
    assert cents_to_usd("88.900050") == Decimal("0.88900050")


def test_claude_usage_cost_reconciliation_without_duplicated_tokens_or_requests(ingested_session):
    source = next(row for row in _claude_usage_rows() if row["server_tool_use"]["web_search_requests"] > 0)
    source_key = _claude_key(source)
    costs = [row for row in _claude_cost_rows() if _claude_key(row) == source_key]
    assert {row["cost_type"] for row in costs} == {"tokens", "web_search"}

    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "claude", UsageFact.source_key == source_key)
    )
    expected_cost = sum(cents_to_usd(row["amount"]) for row in costs)

    assert fact.requests == source["requests"]
    assert fact.total_tokens == source["total_tokens"]
    assert fact.cost_usd == expected_cost
    assert ingested_session.scalar(
        select(func.count()).select_from(UsageFact).where(UsageFact.platform == "claude", UsageFact.source_key == source_key)
    ) == 1


def test_all_claude_cost_rows_match_usage_rows():
    usage_keys = {_claude_key(row) for row in _claude_usage_rows()}
    cost_keys = {_claude_key(row) for row in _claude_cost_rows()}

    assert cost_keys - usage_keys == set()


def test_web_search_cost_affects_cost_but_not_tokens(ingested_session):
    source = next(row for row in _claude_usage_rows() if row["server_tool_use"]["web_search_requests"] > 0)
    source_key = _claude_key(source)
    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "claude", UsageFact.source_key == source_key)
    )

    assert fact.web_search_cost_usd > Decimal("0")
    assert fact.total_tokens == source["total_tokens"]
    assert fact.input_tokens + fact.output_tokens == source["total_tokens"]


def test_gemini_owner_to_user_and_project_to_group_attribution(ingested_session):
    source = _gemini_rows()[0]
    labels = labels_to_dict(source["labels"])
    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "gemini", UsageFact.source_key == _gemini_key(source))
    )

    assert fact.user_id == ingested_session.scalar(select(User.user_id).where(User.email == labels["owner"]))
    assert fact.group_id == "clinical-operations"


def test_gemini_team_label_validation(session, tmp_path):
    copied = tmp_path / "starter-kit"
    shutil.copytree(STARTER_KIT, copied)
    gemini_path = next((copied / "data" / "gemini").glob("*.jsonl"))
    rows = gemini_path.read_text().splitlines()
    first = json.loads(rows[0])
    for label in first["project"]["labels"]:
        if label["key"] == "team":
            label["value"] = "finance"
    rows[0] = json.dumps(first)
    gemini_path.write_text("\n".join(rows) + "\n")

    load_directory(session, copied)
    session.flush()
    with pytest.raises(ValueError, match="team label"):
        ingest_gemini(session, copied)


def test_gemini_input_output_sku_pairing_and_total_tokens(ingested_session):
    input_row = _gemini_rows()[0]
    output_row = _gemini_rows()[1]
    assert _gemini_key(input_row) == _gemini_key(output_row)

    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "gemini", UsageFact.source_key == _gemini_key(input_row))
    )

    assert fact.input_tokens == int(input_row["usage"]["amount"])
    assert fact.output_tokens == int(output_row["usage"]["amount"])
    assert fact.total_tokens == fact.input_tokens + fact.output_tokens


def test_gemini_usd_cost_handling(ingested_session):
    input_row = _gemini_rows()[0]
    output_row = _gemini_rows()[1]
    fact = ingested_session.scalar(
        select(UsageFact).where(UsageFact.platform == "gemini", UsageFact.source_key == _gemini_key(input_row))
    )

    assert fact.input_cost_usd == Decimal(str(input_row["cost"]))
    assert fact.output_cost_usd == Decimal(str(output_row["cost"]))
    assert fact.cost_usd == Decimal(str(input_row["cost"])) + Decimal(str(output_row["cost"]))


def test_all_gemini_skus_are_recognized():
    sku_descriptions = {row["sku"]["description"] for row in _gemini_rows()}

    assert sku_descriptions == {
        "Gemini 2.5 Flash Text Input Tokens - Predictions",
        "Gemini 2.5 Flash Text Output Tokens - Predictions",
        "Gemini 2.5 Pro Text Input Tokens - Predictions",
        "Gemini 2.5 Pro Text Output Tokens - Predictions",
    }


def test_ingestion_idempotency(session):
    ingest_all(session, STARTER_KIT)
    session.commit()
    first_counts = (
        session.scalar(select(func.count()).select_from(User)),
        session.scalar(select(func.count()).select_from(Group)),
        session.scalar(select(func.count()).select_from(UsageFact)),
    )
    first_platform_totals = _platform_totals(session)

    ingest_all(session, STARTER_KIT)
    session.commit()
    second_counts = (
        session.scalar(select(func.count()).select_from(User)),
        session.scalar(select(func.count()).select_from(Group)),
        session.scalar(select(func.count()).select_from(UsageFact)),
    )
    second_platform_totals = _platform_totals(session)

    assert second_counts == first_counts
    assert second_platform_totals == first_platform_totals


def test_claude_ingestion_requires_directory(session):
    with pytest.raises(ValueError, match="unknown or mismatched user"):
        ingest_claude(session, STARTER_KIT)
