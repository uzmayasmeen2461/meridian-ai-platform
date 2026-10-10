import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.authorization import AuthorizationService, Denial
from app.domain.capabilities import CapabilityService, CapabilityState
from app.domain.models import Group, User
from app.domain.policy import CAPABILITIES, SCOPES, EnvironmentPolicy


ENVIRONMENTS = ("dev", "staging", "prod")
PERMISSIONS_MANIFEST = "permissions.manifest.json"
HOST_REGISTRATION = "host-registration.json"


class ProvisioningError(ValueError):
    pass


class ProvisioningDenied(PermissionError):
    def __init__(self, denial: Denial):
        self.denial = denial
        super().__init__(denial.reason)


@dataclass(frozen=True)
class ProvisionedEnvironment:
    environment: str
    permissions_manifest: Path
    host_registration: Path


def provision_environments(
    session: Session,
    *,
    actor_user_id: str,
    starter_kit: Path,
    output_dir: Path,
    database_url: str,
    environments: list[str] | None = None,
    group_id: str | None = None,
) -> list[ProvisionedEnvironment]:
    selected = environments or list(ENVIRONMENTS)
    results = []
    for environment in selected:
        results.append(
            provision_environment(
                session,
                actor_user_id=actor_user_id,
                starter_kit=starter_kit,
                output_dir=output_dir,
                database_url=database_url,
                environment=environment,
                group_id=group_id,
            )
        )
    return results


def provision_environment(
    session: Session,
    *,
    actor_user_id: str,
    starter_kit: Path,
    output_dir: Path,
    database_url: str,
    environment: str,
    group_id: str | None = None,
) -> ProvisionedEnvironment:
    if environment not in ENVIRONMENTS:
        raise ProvisioningError(f"Unsupported environment: {environment}")

    policy = EnvironmentPolicy.from_file(starter_kit / "environments" / f"{environment}.yaml")
    capabilities = CapabilityService(session, policy)
    auth = AuthorizationService(session, policy, capabilities)

    actor = session.get(User, actor_user_id)
    if actor is None:
        raise ProvisioningDenied(Denial(error="permission_denied", reason="Missing or unknown identity."))

    target_groups = authorized_groups(session, auth, actor_user_id, actor, group_id)
    tools_contract = load_tools_contract(starter_kit)

    manifest = permissions_manifest_payload(
        policy=policy,
        groups=target_groups,
        capabilities=capabilities,
        tools_contract=tools_contract,
    )
    registration = host_registration_payload(
        policy=policy,
        database_url=database_url,
        starter_kit=starter_kit,
    )

    validate_manifest(manifest, tools_contract, target_groups)
    validate_host_registration(registration, policy)

    environment_dir = output_dir / environment
    environment_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = environment_dir / PERMISSIONS_MANIFEST
    registration_path = environment_dir / HOST_REGISTRATION
    write_json(manifest_path, manifest)
    write_json(registration_path, registration)

    return ProvisionedEnvironment(
        environment=environment,
        permissions_manifest=manifest_path,
        host_registration=registration_path,
    )


def authorized_groups(
    session: Session,
    auth: AuthorizationService,
    actor_user_id: str,
    actor: User,
    group_id: str | None,
) -> list[Group]:
    if group_id is not None:
        result = auth.authorize_capability_write(actor_user_id, group_id, "usage-connector")
        if not result.allowed:
            assert result.denial is not None
            raise ProvisioningDenied(result.denial)
        assert result.group is not None
        return [result.group]

    if actor.role == "platform_admin":
        groups = session.scalars(select(Group).order_by(Group.group_id.asc())).all()
    else:
        result = auth.authorize_capability_write(actor_user_id, actor.primary_group_id, "usage-connector")
        if not result.allowed:
            assert result.denial is not None
            raise ProvisioningDenied(result.denial)
        assert result.group is not None
        groups = [result.group]

    return list(groups)


def permissions_manifest_payload(
    *,
    policy: EnvironmentPolicy,
    groups: list[Group],
    capabilities: CapabilityService,
    tools_contract: dict[str, Any],
) -> dict[str, Any]:
    tool_scopes = {
        name: {"scope": spec["scope"], "input": spec["input"]}
        for name, spec in sorted(tools_contract["tools"].items())
    }
    return {
        "environment": policy.name,
        "server_name": policy.server_name,
        "scopes": {
            scope: {
                "roles": sorted(policy.roles_for_scope(scope)),
                "group_visibility": policy.group_visibility_for_scope(scope),
            }
            for scope in sorted(SCOPES)
        },
        "groups": [group_payload(group, capabilities) for group in groups],
        "tools": tool_scopes,
    }


def group_payload(group: Group, capabilities: CapabilityService) -> dict[str, Any]:
    states = [capabilities.get_state(group.group_id, capability) for capability in sorted(CAPABILITIES)]
    return {
        "group_id": group.group_id,
        "name": group.name,
        "team_lead_user_id": group.team_lead_user_id,
        "capabilities": [capability_payload(state) for state in states],
    }


def capability_payload(state: CapabilityState) -> dict[str, Any]:
    return {
        "capability": state.capability,
        "enabled": state.enabled,
        "source": "override" if state.updated_at else "yaml_default",
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        "updated_by": state.updated_by,
    }


def host_registration_payload(
    *,
    policy: EnvironmentPolicy,
    database_url: str,
    starter_kit: Path,
) -> dict[str, Any]:
    server_config = {
        "command": "python3",
        "args": ["-m", "app.mcp_server"],
        "transport": "stdio",
        "env": {
            "MERIDIAN_DATABASE_URL": database_url,
            "MERIDIAN_ENV": policy.name,
            "MERIDIAN_STARTER_KIT": str(starter_kit),
            "MERIDIAN_MCP_USER_ID": "<set-by-launcher>",
        },
    }
    return {
        "environment": policy.name,
        "server_name": policy.server_name,
        "claude_desktop": {
            "mcpServers": {
                policy.server_name: server_config,
            }
        },
        "gemini_cli": {
            "mcpServers": {
                policy.server_name: server_config,
            }
        },
    }


def validate_manifest(manifest: dict[str, Any], tools_contract: dict[str, Any], groups: list[Group]) -> None:
    if manifest["environment"] not in ENVIRONMENTS:
        raise ProvisioningError("Manifest has unsupported environment.")

    expected_tools = set(tools_contract["tools"])
    if set(manifest["tools"]) != expected_tools:
        raise ProvisioningError("Manifest tool set does not match the MCP contract.")

    for tool_name, tool in manifest["tools"].items():
        if tool["scope"] != tools_contract["tools"][tool_name]["scope"]:
            raise ProvisioningError(f"Manifest scope mismatch for {tool_name}.")

    expected_groups = {group.group_id for group in groups}
    manifest_groups = {group["group_id"] for group in manifest["groups"]}
    if manifest_groups != expected_groups:
        raise ProvisioningError("Manifest group set does not match authorized groups.")

    for group in manifest["groups"]:
        capabilities = {item["capability"] for item in group["capabilities"]}
        if capabilities != CAPABILITIES:
            raise ProvisioningError(f"Manifest capabilities are incomplete for {group['group_id']}.")


def validate_host_registration(registration: dict[str, Any], policy: EnvironmentPolicy) -> None:
    if registration["environment"] != policy.name:
        raise ProvisioningError("Host registration environment does not match policy.")
    if registration["server_name"] != policy.server_name:
        raise ProvisioningError("Host registration server name does not match policy.")

    for host_key in ("claude_desktop", "gemini_cli"):
        servers = registration[host_key]["mcpServers"]
        if set(servers) != {policy.server_name}:
            raise ProvisioningError(f"{host_key} registration has an unexpected server set.")
        server = servers[policy.server_name]
        if server["transport"] != "stdio":
            raise ProvisioningError(f"{host_key} registration must use stdio.")
        if server["env"]["MERIDIAN_ENV"] != policy.name:
            raise ProvisioningError(f"{host_key} MERIDIAN_ENV does not match policy.")


def load_tools_contract(starter_kit: Path) -> dict[str, Any]:
    with (starter_kit / "contracts" / "tools.schema.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    path.write_text(rendered, encoding="utf-8")
