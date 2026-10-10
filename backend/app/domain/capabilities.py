from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import CapabilityOverride, Group, User
from app.domain.policy import CAPABILITIES, EnvironmentPolicy


@dataclass(frozen=True)
class CapabilityState:
    group_id: str
    capability: str
    enabled: bool
    updated_at: datetime | None
    updated_by: str | None
    source: str


class CapabilityService:
    def __init__(self, session: Session, policy: EnvironmentPolicy):
        self.session = session
        self.policy = policy

    def get_state(self, group_id: str, capability: str) -> CapabilityState:
        if capability not in CAPABILITIES:
            raise ValueError(f"Unknown capability: {capability}")
        if self.session.get(Group, group_id) is None:
            raise ValueError(f"Unknown group: {group_id}")

        override = self.session.scalar(
            select(CapabilityOverride).where(
                CapabilityOverride.group_id == group_id,
                CapabilityOverride.capability == capability,
            )
        )
        if override is not None:
            return CapabilityState(
                group_id=group_id,
                capability=capability,
                enabled=override.enabled,
                updated_at=override.updated_at,
                updated_by=override.updated_by,
                source="override",
            )

        return CapabilityState(
            group_id=group_id,
            capability=capability,
            enabled=self.policy.default_capability_enabled(group_id, capability),
            updated_at=None,
            updated_by=None,
            source="default",
        )

    def list_group_states(self, group_id: str) -> list[CapabilityState]:
        return [self.get_state(group_id, capability) for capability in sorted(CAPABILITIES)]

    def set_override(self, group_id: str, capability: str, enabled: bool, updated_by: User) -> CapabilityState:
        if capability not in CAPABILITIES:
            raise ValueError(f"Unknown capability: {capability}")
        if self.session.get(Group, group_id) is None:
            raise ValueError(f"Unknown group: {group_id}")

        override = self.session.scalar(
            select(CapabilityOverride).where(
                CapabilityOverride.group_id == group_id,
                CapabilityOverride.capability == capability,
            )
        )
        if override is None:
            override = CapabilityOverride(group_id=group_id, capability=capability)
        override.enabled = enabled
        override.updated_by = updated_by.user_id
        self.session.add(override)
        self.session.flush()
        return self.get_state(group_id, capability)
