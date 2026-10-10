from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.environment import load_environment_policy


CAPABILITIES = {"usage-connector", "web-search", "code-execution"}
SCOPES = {"usage:read", "capabilities:write"}


@dataclass(frozen=True)
class EnvironmentPolicy:
    name: str
    scopes: dict[str, Any]
    capability_defaults: dict[str, Any]
    server_name: str

    @classmethod
    def from_file(cls, path: Path) -> "EnvironmentPolicy":
        payload = load_environment_policy(path)
        return cls(
            name=payload["environment"],
            scopes=payload["scopes"],
            capability_defaults=payload["capability_defaults"],
            server_name=payload["host"]["server_name"],
        )

    def roles_for_scope(self, scope: str) -> set[str]:
        return set(self.scopes.get(scope, {}).get("roles", []))

    def group_visibility_for_scope(self, scope: str) -> str:
        return self.scopes.get(scope, {}).get("group_visibility", "own_group")

    def default_capability_enabled(self, group_id: str, capability: str) -> bool:
        value = self.capability_defaults.get(capability)
        if value == "enabled":
            return True
        if value == "disabled":
            return False
        if isinstance(value, dict) and "enabled_for" in value:
            return group_id in value["enabled_for"]
        return False
