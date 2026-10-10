import json
import os
from decimal import Decimal
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field
from typing_extensions import Literal

from app.core.database import make_session_factory
from app.core.settings import environment_policy_path, get_settings
from app.domain.authorization import AuthorizationResult, Denial, permission_denied
from app.domain.capabilities import CapabilityState
from app.domain.periods import parse_period
from app.domain.policy import CAPABILITIES, EnvironmentPolicy
from app.domain.usage import PlatformTotals, UsageService, combined_totals


GroupId = Literal[
    "clinical-operations",
    "regulatory-affairs",
    "finance",
    "hr",
    "medical-writing",
    "it-platform",
]
CapabilityName = Literal["usage-connector", "web-search", "code-execution"]
Period = Annotated[str, Field(pattern=r"^(last_7_days|last_30_days|\d{4}-W\d{2}|\d{4}-\d{2})$")]
Limit = Annotated[int, Field(ge=1, le=25)]


def mcp_identity_user_id() -> str | None:
    return os.getenv("MERIDIAN_MCP_USER_ID")


def create_mcp_server() -> MCPServer:
    settings = get_settings()
    policy = EnvironmentPolicy.from_file(environment_policy_path(settings))
    server = MCPServer(policy.server_name)

    @server.tool(
        name="usage_summary",
        description="Return Claude and Gemini token and cost totals for one group and period.",
    )
    def usage_summary(period: Period, group: GroupId | None = None) -> str:
        return json_result(read_usage_summary(group, period))

    @server.tool(
        name="top_users",
        description="Return users ranked by total tokens for one group and period.",
    )
    def top_users(period: Period, group: GroupId | None = None, limit: Limit = 10) -> str:
        return json_result(read_top_users(group, period, limit))

    @server.tool(
        name="capability_status",
        description="Return current capability states for one group.",
    )
    def capability_status(group: GroupId | None = None) -> str:
        return json_result(read_capability_status(group))

    @server.tool(
        name="set_capability",
        description="Persist a capability override for one group.",
    )
    def set_capability(group: GroupId, capability: CapabilityName, enabled: bool) -> str:
        return json_result(write_capability(group, capability, enabled))

    return server


def read_usage_summary(group: str | None, period: str) -> dict:
    with ServiceContext() as context:
        result = context.authorize("usage:read", group)
        if not result.allowed:
            return denial_payload(result.denial)

        period_range = parse_period_or_denial(period, "usage:read")
        if isinstance(period_range, dict):
            return period_range

        usage = UsageService(context.session)
        assert result.group is not None
        platforms = usage.platform_totals(result.group.group_id, period_range)
        return {
            "group": result.group.group_id,
            "period": {
                "start": period_range.start.isoformat(),
                "end_exclusive": period_range.end_exclusive.isoformat(),
            },
            "platforms": [platform_payload(item) for item in platforms],
            "totals": summary_totals_payload(combined_totals(platforms)),
        }


def read_top_users(group: str | None, period: str, limit: int) -> dict | list[dict]:
    if limit < 1 or limit > 25:
        return denial_payload(Denial(error="permission_denied", reason="Invalid limit.", required_scope="usage:read"))

    with ServiceContext() as context:
        result = context.authorize("usage:read", group)
        if not result.allowed:
            return denial_payload(result.denial)

        period_range = parse_period_or_denial(period, "usage:read")
        if isinstance(period_range, dict):
            return period_range

        assert result.group is not None
        users = UsageService(context.session).top_users(result.group.group_id, period_range, limit)
        return [
            {
                "user_id": user.user_id,
                "name": user.name,
                "email": user.email,
                "group": user.group,
                "total_tokens": user.total_tokens,
                "cost_usd": cost_payload(user.cost_usd),
            }
            for user in users
        ]


def read_capability_status(group: str | None) -> dict | list[dict]:
    with ServiceContext() as context:
        result = context.authorize("usage:read", group)
        if not result.allowed:
            return denial_payload(result.denial)

        assert result.group is not None
        states = context.capabilities.list_group_states(result.group.group_id)
        return [capability_payload(state) for state in states]


def write_capability(group: str, capability: str, enabled: bool) -> dict:
    if capability not in CAPABILITIES:
        return denial_payload(Denial(error="permission_denied", reason="Unknown capability.", required_scope="capabilities:write"))

    with ServiceContext() as context:
        result = context.authorize("capabilities:write", group)
        if not result.allowed:
            return denial_payload(result.denial)

        assert result.group is not None
        assert result.user is not None
        state = context.capabilities.set_override(result.group.group_id, capability, enabled, result.user)
        context.session.commit()
        return capability_payload(state)


class ServiceContext:
    def __init__(self):
        settings = get_settings()
        self.policy = EnvironmentPolicy.from_file(environment_policy_path(settings))
        self.session_factory = make_session_factory(settings.database_url)
        self.session = None
        self.capabilities = None
        self.auth = None

    def __enter__(self):
        from app.domain.authorization import AuthorizationService
        from app.domain.capabilities import CapabilityService

        self.session = self.session_factory()
        self.capabilities = CapabilityService(self.session, self.policy)
        self.auth = AuthorizationService(self.session, self.policy, self.capabilities)
        return self

    def __exit__(self, exc_type, exc, tb):
        assert self.session is not None
        self.session.close()

    def authorize(self, scope: str, group: str | None) -> AuthorizationResult:
        assert self.auth is not None
        return self.auth.authorize_mcp_operation(mcp_identity_user_id(), scope, group)


def parse_period_or_denial(period: str, scope: str):
    try:
        return parse_period(period)
    except ValueError:
        return denial_payload(Denial(error="permission_denied", reason="Invalid period.", required_scope=scope))


def platform_payload(item: PlatformTotals) -> dict:
    return {
        "platform": item.platform,
        "requests": item.requests,
        "input_tokens": item.input_tokens,
        "output_tokens": item.output_tokens,
        "total_tokens": item.total_tokens,
        "cost_usd": cost_payload(item.cost_usd),
    }


def summary_totals_payload(totals: dict) -> dict:
    return {
        "total_tokens": int(totals.get("total_tokens", 0)),
        "cost_usd": cost_payload(totals.get("cost_usd", Decimal("0"))),
    }


def capability_payload(state: CapabilityState) -> dict:
    return {
        "group": state.group_id,
        "capability": state.capability,
        "enabled": state.enabled,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        "updated_by": state.updated_by,
    }


def denial_payload(denial: Denial | None) -> dict:
    if denial is None:
        denial = permission_denied("Permission denied.").denial
    assert denial is not None
    return denial.as_dict()


def cost_payload(value: Decimal | int | None) -> float:
    return float(value or Decimal("0"))


def json_result(payload: dict | list[dict]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
