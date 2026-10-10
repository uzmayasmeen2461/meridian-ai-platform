from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domain.models import Group, UsageFact, User
from app.ingest.directory import load_directory
from app.ingest.loader import ingest_all
from app.main import app

STARTER_KIT = Path(__file__).resolve().parents[2] / "starter-kit"

USERS = {
    "clinical_lead": "user_E7691888F28227066DD2FB86",
    "clinical_member": "user_699C48763F6FA2958D2CDB5D",
    "finance_lead": "user_0CF0516C4D9067BED584DB3F",
    "admin": "user_533B58E6F66C98ACB833527A",
}


@pytest.fixture()
def api_db(tmp_path, monkeypatch):
    db_path = tmp_path / "api.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ingest_all(session, STARTER_KIT)
        session.commit()

    monkeypatch.setenv("MERIDIAN_DATABASE_URL", database_url)
    monkeypatch.setenv("MERIDIAN_STARTER_KIT", str(STARTER_KIT))
    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    return database_url


@pytest.fixture()
def client(api_db):
    return TestClient(app)


def _headers(user_id: str):
    return {"X-User-Id": user_id}


def _direct_platform_totals(database_url: str, group_id: str, start: date, end: date):
    engine = create_engine(database_url)
    with Session(engine) as session:
        rows = session.execute(
            select(
                UsageFact.platform,
                func.sum(UsageFact.input_tokens),
                func.sum(UsageFact.output_tokens),
                func.sum(UsageFact.total_tokens),
                func.sum(UsageFact.cost_usd),
            )
            .where(UsageFact.group_id == group_id, UsageFact.usage_date >= start, UsageFact.usage_date < end)
            .group_by(UsageFact.platform)
        ).all()
    return {
        row.platform: {
            "input_tokens": int(row[1] or 0),
            "output_tokens": int(row[2] or 0),
            "total_tokens": int(row[3] or 0),
            "cost_usd": float((row[4] or Decimal("0")).quantize(Decimal("0.000001"))),
        }
        for row in rows
    }


def test_health_endpoint(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_me_accepts_user_id_or_email_and_rejects_conflict(client):
    by_id = client.get("/api/me", headers=_headers(USERS["clinical_lead"]))
    by_email = client.get("/api/me", headers={"X-User-Email": "priya.nair@meridianls.example"})
    conflict = client.get(
        "/api/me",
        headers={"X-User-Id": USERS["clinical_lead"], "X-User-Email": "sofia.rossi@meridianls.example"},
    )

    assert by_id.status_code == 200
    assert by_id.json()["email"] == "priya.nair@meridianls.example"
    assert by_email.status_code == 200
    assert by_email.json()["user_id"] == USERS["clinical_lead"]
    assert conflict.status_code == 403
    assert conflict.json()["error"] == "permission_denied"


def test_summary_reconciles_with_direct_sql(client, api_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")

    response = client.get(
        "/api/usage/summary",
        params={"group_id": "clinical-operations", "period": "last_7_days"},
        headers=_headers(USERS["admin"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["group"] == "clinical-operations"
    assert body["period"] == {"start": "2026-09-21", "end_exclusive": "2026-09-28"}
    direct = _direct_platform_totals(api_db, "clinical-operations", date(2026, 9, 21), date(2026, 9, 28))
    by_platform = {item["platform"]: item for item in body["platforms"]}
    for platform in ("claude", "gemini"):
        assert by_platform[platform]["input_tokens"] == direct[platform]["input_tokens"]
        assert by_platform[platform]["output_tokens"] == direct[platform]["output_tokens"]
        assert by_platform[platform]["total_tokens"] == direct[platform]["total_tokens"]
        assert by_platform[platform]["cost_usd"] == direct[platform]["cost_usd"]
    assert by_platform["gemini"]["requests"] is None
    assert body["totals"]["total_tokens"] == sum(item["total_tokens"] for item in body["platforms"])


def test_period_parsing_week_month_and_unsupported(client):
    week = client.get(
        "/api/usage/summary",
        params={"group_id": "clinical-operations", "period": "2026-W36"},
        headers=_headers(USERS["clinical_member"]),
    )
    month = client.get(
        "/api/usage/summary",
        params={"group_id": "clinical-operations", "period": "2026-09"},
        headers=_headers(USERS["clinical_member"]),
    )
    bad = client.get(
        "/api/usage/summary",
        params={"group_id": "clinical-operations", "period": "yesterday"},
        headers=_headers(USERS["clinical_member"]),
    )

    assert week.status_code == 200
    assert week.json()["period"] == {"start": "2026-08-31", "end_exclusive": "2026-09-07"}
    assert month.status_code == 200
    assert month.json()["period"] == {"start": "2026-09-01", "end_exclusive": "2026-10-01"}
    assert bad.status_code == 422


def test_weekly_results_are_chronological_and_platform_filter_works(client):
    response = client.get(
        "/api/usage/by-week",
        params={"group_id": "clinical-operations", "platform": "gemini"},
        headers=_headers(USERS["clinical_member"]),
    )
    bad_platform = client.get(
        "/api/usage/by-week",
        params={"group_id": "clinical-operations", "platform": "openai"},
        headers=_headers(USERS["clinical_member"]),
    )

    assert response.status_code == 200
    weeks = response.json()
    assert [item["week"] for item in weeks] == sorted(item["week"] for item in weeks)
    assert all([platform["platform"] == "gemini" for item in weeks for platform in item["platforms"]])
    assert bad_platform.status_code == 422


def test_environment_authorization_for_usage_routes(client, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    dev_member = client.get(
        "/api/usage/summary",
        params={"group_id": "finance", "period": "last_7_days"},
        headers=_headers(USERS["clinical_member"]),
    )
    monkeypatch.setenv("MERIDIAN_ENV", "staging")
    staging_member = client.get(
        "/api/usage/summary",
        params={"group_id": "clinical-operations", "period": "last_7_days"},
        headers=_headers(USERS["clinical_member"]),
    )
    staging_own = client.get(
        "/api/usage/summary",
        params={"period": "last_7_days"},
        headers=_headers(USERS["clinical_lead"]),
    )
    staging_cross = client.get(
        "/api/usage/summary",
        params={"group_id": "finance", "period": "last_7_days"},
        headers=_headers(USERS["clinical_lead"]),
    )

    assert dev_member.status_code == 200
    assert staging_member.status_code == 403
    assert staging_own.status_code == 200
    assert staging_own.json()["group"] == "clinical-operations"
    assert staging_cross.status_code == 403
    assert staging_cross.json() == {
        "error": "permission_denied",
        "reason": "Caller may not access the requested group.",
        "required_scope": "usage:read",
    }


def test_prod_authorization_and_no_usage_connector_gate_for_rest_usage(client, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")

    finance_lead_usage = client.get(
        "/api/usage/summary",
        params={"period": "last_7_days"},
        headers=_headers(USERS["finance_lead"]),
    )
    finance_lead_write = client.put(
        "/api/capabilities/finance/code-execution",
        json={"enabled": True},
        headers=_headers(USERS["finance_lead"]),
    )
    admin_write = client.put(
        "/api/capabilities/finance/code-execution",
        json={"enabled": True},
        headers=_headers(USERS["admin"]),
    )

    assert finance_lead_usage.status_code == 200
    assert finance_lead_usage.json()["group"] == "finance"
    assert finance_lead_write.status_code == 403
    assert admin_write.status_code == 200
    assert admin_write.json()["enabled"] is True


def test_missing_invalid_identities_and_unknown_group_fail_closed(client, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")

    missing = client.get("/api/groups")
    invalid = client.get("/api/groups", headers={"X-User-Id": "not-a-user"})
    unknown_group = client.get(
        "/api/usage/summary",
        params={"group_id": "not-a-group", "period": "last_7_days"},
        headers=_headers(USERS["admin"]),
    )

    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert unknown_group.status_code == 403
    assert missing.json()["error"] == "permission_denied"
    assert invalid.json()["error"] == "permission_denied"
    assert unknown_group.json()["error"] == "permission_denied"


def test_capability_read_write_permissions_and_persistence(client, api_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")

    before = client.get("/api/capabilities", params={"group_id": "finance"}, headers=_headers(USERS["admin"]))
    write = client.put(
        "/api/capabilities/finance/usage-connector",
        json={"enabled": True},
        headers=_headers(USERS["admin"]),
    )
    after_restart = TestClient(app).get(
        "/api/capabilities",
        params={"group_id": "finance"},
        headers=_headers(USERS["admin"]),
    )
    bad_capability = client.put(
        "/api/capabilities/finance/nope",
        json={"enabled": True},
        headers=_headers(USERS["admin"]),
    )

    assert before.status_code == 200
    assert next(item for item in before.json() if item["capability"] == "usage-connector")["enabled"] is False
    assert write.status_code == 200
    assert write.json()["updated_by"] == USERS["admin"]
    assert next(item for item in after_restart.json() if item["capability"] == "usage-connector")["enabled"] is True
    assert bad_capability.status_code == 422


def test_top_users_sorting_and_limit_validation(client, api_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "dev")

    response = client.get(
        "/api/usage/top-users",
        params={"group_id": "clinical-operations", "period": "last_30_days", "limit": 3},
        headers=_headers(USERS["clinical_member"]),
    )
    bad_low = client.get(
        "/api/usage/top-users",
        params={"group_id": "clinical-operations", "period": "last_30_days", "limit": 0},
        headers=_headers(USERS["clinical_member"]),
    )
    bad_high = client.get(
        "/api/usage/top-users",
        params={"group_id": "clinical-operations", "period": "last_30_days", "limit": 26},
        headers=_headers(USERS["clinical_member"]),
    )

    assert response.status_code == 200
    users = response.json()
    assert len(users) == 3
    assert users == sorted(users, key=lambda row: (-row["total_tokens"], row["name"], row["user_id"]))
    assert bad_low.status_code == 422
    assert bad_high.status_code == 422


def test_denied_responses_do_not_leak_protected_data(client, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")

    response = client.get(
        "/api/usage/top-users",
        params={"group_id": "finance", "period": "last_30_days"},
        headers=_headers(USERS["clinical_lead"]),
    )

    assert response.status_code == 403
    body = response.json()
    assert body == {
        "error": "permission_denied",
        "reason": "Caller may not access the requested group.",
        "required_scope": "usage:read",
    }
    assert "finance" not in str(body)
    assert "sofia.rossi" not in str(body)


def test_openapi_contains_phase_three_endpoints(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/health" in paths
    assert "/api/me" in paths
    assert "/api/groups" in paths
    assert "/api/usage/summary" in paths
    assert "/api/usage/by-week" in paths
    assert "/api/usage/top-users" in paths
    assert "/api/capabilities" in paths
    assert "/api/capabilities/{group_id}/{capability}" in paths
