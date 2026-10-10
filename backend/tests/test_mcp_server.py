import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.core.database import Base, make_engine, make_session_factory
from app.ingest.loader import ingest_all
from app.mcp_server import create_mcp_server, read_top_users


REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_KIT = REPO_ROOT / "starter-kit"
ADMIN = "user_533B58E6F66C98ACB833527A"
CLINICAL_LEAD = "user_E7691888F28227066DD2FB86"
HR_LEAD = "user_EFD3FFD905F1F3A62F1AE916"
MEMBER = "user_699C48763F6FA2958D2CDB5D"


@pytest.fixture()
def mcp_db(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'mcp.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = make_session_factory(database_url)
    with factory() as session:
        ingest_all(session, STARTER_KIT)
        session.commit()

    monkeypatch.setenv("MERIDIAN_DATABASE_URL", database_url)
    monkeypatch.setenv("MERIDIAN_STARTER_KIT", str(STARTER_KIT))
    return database_url


async def call_tool(name: str, arguments: dict):
    server = create_mcp_server()
    result = await server.call_tool(name, arguments)
    assert result.content
    return json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_usage_summary_allowed_for_admin(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", ADMIN)

    payload = await call_tool(
        "usage_summary",
        {"group": "clinical-operations", "period": "last_7_days"},
    )

    assert payload["group"] == "clinical-operations"
    assert payload["period"] == {"start": "2026-09-21", "end_exclusive": "2026-09-28"}
    assert {item["platform"] for item in payload["platforms"]} == {"claude", "gemini"}
    assert payload["totals"]["total_tokens"] == sum(item["total_tokens"] for item in payload["platforms"])
    assert payload["totals"]["cost_usd"] == pytest.approx(sum(item["cost_usd"] for item in payload["platforms"]))


@pytest.mark.anyio
async def test_cross_group_denial_contains_no_usage_data(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", CLINICAL_LEAD)

    payload = await call_tool(
        "usage_summary",
        {"group": "finance", "period": "last_7_days"},
    )

    assert payload == {
        "error": "permission_denied",
        "reason": "Caller may not access the requested group.",
        "required_scope": "usage:read",
    }
    assert "platforms" not in payload
    assert "tokens" not in json.dumps(payload).lower()
    assert "cost" not in json.dumps(payload).lower()


@pytest.mark.anyio
async def test_omitted_group_is_scoped_to_callers_group(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", CLINICAL_LEAD)

    payload = await call_tool("usage_summary", {"period": "last_7_days"})

    assert payload["group"] == "clinical-operations"


@pytest.mark.anyio
async def test_usage_connector_disabled_blocks_mcp_operations(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", HR_LEAD)

    payload = await call_tool("capability_status", {"group": "hr"})

    assert payload == {
        "error": "permission_denied",
        "reason": "usage-connector is disabled for the caller's group.",
        "required_scope": "usage:read",
    }


@pytest.mark.anyio
async def test_capability_override_allows_later_mcp_read(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", ADMIN)

    update = await call_tool(
        "set_capability",
        {"group": "hr", "capability": "usage-connector", "enabled": True},
    )
    assert update["group"] == "hr"
    assert update["capability"] == "usage-connector"
    assert update["enabled"] is True
    assert update["updated_by"] == ADMIN

    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", HR_LEAD)
    payload = await call_tool("usage_summary", {"period": "last_7_days"})

    assert payload["group"] == "hr"


@pytest.mark.anyio
async def test_team_lead_write_denied_in_prod(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", CLINICAL_LEAD)

    payload = await call_tool(
        "set_capability",
        {"group": "clinical-operations", "capability": "web-search", "enabled": False},
    )

    assert payload == {
        "error": "permission_denied",
        "reason": "Caller role is not allowed for this operation.",
        "required_scope": "capabilities:write",
    }


@pytest.mark.anyio
async def test_member_write_denied_in_dev(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", MEMBER)

    payload = await call_tool(
        "set_capability",
        {"group": "clinical-operations", "capability": "web-search", "enabled": False},
    )

    assert payload["error"] == "permission_denied"
    assert payload["required_scope"] == "capabilities:write"


@pytest.mark.anyio
async def test_missing_and_unknown_identity_fail_closed(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    monkeypatch.delenv("MERIDIAN_MCP_USER_ID", raising=False)
    missing = await call_tool("usage_summary", {"period": "last_7_days"})
    assert missing["error"] == "permission_denied"
    assert "identity" in missing["reason"].lower()

    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", "not-a-user")
    unknown = await call_tool("usage_summary", {"period": "last_7_days"})
    assert unknown["error"] == "permission_denied"
    assert "identity" in unknown["reason"].lower()


def test_invalid_period_returns_denial(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", ADMIN)

    payload = read_top_users("clinical-operations", "2026-W99", 10)

    assert payload == {
        "error": "permission_denied",
        "reason": "Invalid period.",
        "required_scope": "usage:read",
    }


@pytest.mark.anyio
async def test_mcp_tool_input_schemas_match_contract(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    server = create_mcp_server()
    tools = {tool.name: tool for tool in await server.list_tools()}
    contract = json.loads((STARTER_KIT / "contracts" / "tools.schema.json").read_text())

    assert set(tools) == set(contract["tools"])
    for name, tool_contract in contract["tools"].items():
        schema = tools[name].input_schema
        expected = tool_contract["input"]
        assert schema["type"] == "object"
        assert schema.get("required", []) == expected.get("required", [])
        validator = Draft202012Validator(schema)
        validator.check_schema(schema)

    usage_schema = tools["usage_summary"].input_schema
    assert usage_schema["properties"]["period"]["pattern"] == contract["$defs"]["Period"]["pattern"]
    assert usage_schema["properties"]["group"]["anyOf"][0]["enum"] == contract["$defs"]["GroupId"]["enum"]

    top_users_schema = tools["top_users"].input_schema
    assert top_users_schema["properties"]["limit"]["minimum"] == 1
    assert top_users_schema["properties"]["limit"]["maximum"] == 25
    assert top_users_schema["properties"]["limit"]["default"] == 10


@pytest.mark.anyio
async def test_mcp_outputs_validate_against_source_contract(mcp_db, monkeypatch):
    monkeypatch.setenv("MERIDIAN_ENV", "prod")
    monkeypatch.setenv("MERIDIAN_MCP_USER_ID", ADMIN)
    contract = json.loads((STARTER_KIT / "contracts" / "tools.schema.json").read_text())

    def output_schema(tool_name: str) -> dict:
        return {"$defs": contract["$defs"], **contract["tools"][tool_name]["output"]}

    summary = await call_tool("usage_summary", {"group": "clinical-operations", "period": "last_7_days"})
    Draft202012Validator(output_schema("usage_summary")).validate(summary)

    users = await call_tool("top_users", {"group": "clinical-operations", "period": "last_7_days", "limit": 3})
    Draft202012Validator(output_schema("top_users")).validate(users)

    capabilities = await call_tool("capability_status", {"group": "clinical-operations"})
    Draft202012Validator(output_schema("capability_status")).validate(capabilities)

    update = await call_tool(
        "set_capability",
        {"group": "clinical-operations", "capability": "web-search", "enabled": False},
    )
    Draft202012Validator(output_schema("set_capability")).validate(update)
