from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.capabilities import CapabilityService
from app.domain.models import Group, User
from app.domain.policy import CAPABILITIES, SCOPES, EnvironmentPolicy


@dataclass(frozen=True)
class Denial:
    error: str
    reason: str
    required_scope: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"error": self.error, "reason": self.reason}
        if self.required_scope is not None:
            payload["required_scope"] = self.required_scope
        return payload


@dataclass(frozen=True)
class AuthorizationResult:
    allowed: bool
    user: User | None = None
    group: Group | None = None
    denial: Denial | None = None


def permission_denied(reason: str, required_scope: str | None = None) -> AuthorizationResult:
    return AuthorizationResult(
        allowed=False,
        denial=Denial(error="permission_denied", reason=reason, required_scope=required_scope),
    )


class AuthorizationService:
    def __init__(self, session: Session, policy: EnvironmentPolicy, capability_service: CapabilityService):
        self.session = session
        self.policy = policy
        self.capability_service = capability_service

    def resolve_identity(self, user_id: str | None) -> User | None:
        if not user_id:
            return None
        return self.session.get(User, user_id)

    def authorize_scope(self, user_id: str | None, scope: str, target_group_id: str | None = None) -> AuthorizationResult:
        if scope not in SCOPES:
            return permission_denied("Unknown scope.", scope)

        user = self.resolve_identity(user_id)
        if user is None:
            return permission_denied("Missing or unknown identity.", scope)

        allowed_roles = self.policy.roles_for_scope(scope)
        if user.role not in allowed_roles:
            return permission_denied("Caller role is not allowed for this operation.", scope)

        group_id = target_group_id or user.primary_group_id
        group = self.session.get(Group, group_id)
        if group is None:
            return permission_denied("Unknown group.", scope)

        if not self._can_see_group(user, group.group_id, scope):
            return permission_denied("Caller may not access the requested group.", scope)

        return AuthorizationResult(allowed=True, user=user, group=group)

    def authorize_capability_write(
        self,
        user_id: str | None,
        group_id: str,
        capability: str,
    ) -> AuthorizationResult:
        if capability not in CAPABILITIES:
            return permission_denied("Unknown capability.", "capabilities:write")
        return self.authorize_scope(user_id, "capabilities:write", group_id)

    def authorize_mcp_operation(
        self,
        user_id: str | None,
        scope: str,
        target_group_id: str | None = None,
    ) -> AuthorizationResult:
        result = self.authorize_scope(user_id, scope, target_group_id)
        if not result.allowed:
            return result

        assert result.user is not None
        usage_connector = self.capability_service.get_state(result.user.primary_group_id, "usage-connector")
        if not usage_connector.enabled:
            return permission_denied("usage-connector is disabled for the caller's group.", scope)

        return result

    def _can_see_group(self, user: User, group_id: str, scope: str) -> bool:
        if user.role == "platform_admin":
            return True

        visibility = self.policy.group_visibility_for_scope(scope)
        if visibility == "all":
            return True
        if visibility == "own_group":
            return user.primary_group_id == group_id
        return False
