from collections.abc import Generator
from typing import Annotated

from fastapi import Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import make_session_factory
from app.core.settings import environment_policy_path, get_settings
from app.domain.authorization import AuthorizationService, permission_denied
from app.domain.capabilities import CapabilityService
from app.domain.models import User
from app.domain.policy import EnvironmentPolicy
from app.domain.usage import UsageService


UserIdHeader = Annotated[str | None, Header(alias="X-User-Id")]
UserEmailHeader = Annotated[str | None, Header(alias="X-User-Email")]


def get_db() -> Generator[Session, None, None]:
    session_factory = make_session_factory(get_settings().database_url)
    with session_factory() as session:
        yield session


def get_policy() -> EnvironmentPolicy:
    settings = get_settings()
    return EnvironmentPolicy.from_file(environment_policy_path(settings))


def get_capability_service(session: Session, policy: EnvironmentPolicy) -> CapabilityService:
    return CapabilityService(session, policy)


def get_authorization_service(session: Session, policy: EnvironmentPolicy) -> AuthorizationService:
    capabilities = get_capability_service(session, policy)
    return AuthorizationService(session, policy, capabilities)


def get_usage_service(session: Session) -> UsageService:
    return UsageService(session)


def resolve_identity_user_id(session: Session, user_id: str | None, email: str | None):
    if user_id and email:
        user = session.get(User, user_id)
        if user is None or user.email != email:
            return permission_denied("Conflicting identity headers.")
        return user.user_id
    if user_id:
        return user_id
    if email:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            return permission_denied("Missing or unknown identity.")
        return user.user_id
    return permission_denied("Missing or unknown identity.")
