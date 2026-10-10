import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_KIT = REPO_ROOT / "starter-kit"
CLAUDE_MANIFEST = REPO_ROOT / "packaging" / "claude-desktop" / "manifest.json"
GEMINI_EXTENSION = REPO_ROOT / "packaging" / "gemini-cli" / "meridian-usage" / "gemini-extension.json"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def contract_tool_names() -> set[str]:
    contract = json.loads((STARTER_KIT / "contracts" / "tools.schema.json").read_text(encoding="utf-8"))
    return set(contract["tools"])


def test_claude_desktop_manifest_matches_mcp_tool_contract():
    manifest = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == "0.3"
    assert manifest["name"] == "meridian-usage"
    assert manifest["server"]["mcp_config"]["command"] == "python3"
    assert set(manifest["server"]["mcp_config"]["env"]) == {
        "PYTHONPATH",
        "MERIDIAN_DATABASE_URL",
        "MERIDIAN_ENV",
        "MERIDIAN_STARTER_KIT",
        "MERIDIAN_MCP_USER_ID",
    }
    assert {tool["name"] for tool in manifest["tools"]} == contract_tool_names()


def test_gemini_extension_registers_meridian_mcp_server():
    extension = json.loads(GEMINI_EXTENSION.read_text(encoding="utf-8"))

    assert extension["name"] == "meridian-usage"
    assert extension["contextFileName"] == "GEMINI.md"
    assert extension["settings"][0]["envVar"] == "MERIDIAN_MCP_USER_ID"
    server = extension["mcpServers"]["meridian-usage"]
    assert server["command"] == "python3"
    assert server["args"] == ["-m", "app.mcp_server"]
    assert server["env"]["MERIDIAN_ENV"] == "prod"
    assert "MERIDIAN_MCP_USER_ID" in server["env"]


def test_ci_workflow_runs_required_validation_steps():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "python -m pytest backend" in workflow
    assert "python -m app.cli provision" in workflow
    assert "npm test" in workflow
    assert "npm run build" in workflow
