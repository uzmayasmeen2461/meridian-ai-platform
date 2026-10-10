from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    UserEmailHeader,
    UserIdHeader,
    get_authorization_service,
    get_capability_service,
    get_db,
    get_policy,
    get_usage_service,
    resolve_identity_user_id,
)
from app.domain.authorization import AuthorizationResult, permission_denied
from app.domain.capabilities import CapabilityService, CapabilityState
from app.domain.models import Group, User
from app.domain.periods import parse_period
from app.domain.policy import CAPABILITIES, EnvironmentPolicy
from app.domain.schemas import (
    CapabilityStateResponse,
    CapabilityUpdateRequest,
    CombinedTotalsResponse,
    DenialResponse,
    GroupResponse,
    PlatformTotalsResponse,
    TopUserResponse,
    UsageSummaryResponse,
    UserResponse,
    WeeklyUsageResponse,
)
from app.domain.usage import PLATFORMS, PlatformTotals, UsageService, combined_totals


router = APIRouter(prefix="/api")


def _cost(value: Decimal) -> float:
    return float(value)


def _denial(result: AuthorizationResult, status_code: int = 403) -> JSONResponse:
    assert result.denial is not None
    return JSONResponse(status_code=status_code, content=result.denial.as_dict())


def _identity_or_denial(session: Session, user_id: str | None, email: str | None):
    return resolve_identity_user_id(session, user_id, email)


def _platform_response(item: PlatformTotals) -> PlatformTotalsResponse:
    return PlatformTotalsResponse(
        platform=item.platform,
        requests=item.requests,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        total_tokens=item.total_tokens,
        cost_usd=_cost(item.cost_usd),
    )


def _totals_response(totals: dict) -> CombinedTotalsResponse:
    return CombinedTotalsResponse(
        input_tokens=int(totals.get("input_tokens", 0)),
        output_tokens=int(totals.get("output_tokens", 0)),
        total_tokens=int(totals.get("total_tokens", 0)),
        cost_usd=_cost(totals.get("cost_usd", Decimal("0"))),
    )


def _capability_response(state: CapabilityState) -> CapabilityStateResponse:
    return CapabilityStateResponse(
        group=state.group_id,
        capability=state.capability,
        enabled=state.enabled,
        updated_at=state.updated_at,
        updated_by=state.updated_by,
    )


def _period_or_422(period: str):
    try:
        return parse_period(period)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/me",
    response_model=UserResponse,
    responses={403: {"model": DenialResponse}},
)
def get_me(
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
):
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)
    user = session.get(User, identity)
    if user is None:
        return _denial(permission_denied("Missing or unknown identity."))
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        role=user.role,
        group_id=user.primary_group_id,
    )


@router.get(
    "/groups",
    response_model=list[GroupResponse],
    responses={403: {"model": DenialResponse}},
)
def get_groups(
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
    policy: EnvironmentPolicy = Depends(get_policy),
):
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)
    auth = get_authorization_service(session, policy)
    user = session.get(User, identity)
    if user is None:
        return _denial(auth.authorize_scope(identity, "usage:read"))

    role_check = auth.authorize_scope(identity, "usage:read", user.primary_group_id)
    if not role_check.allowed:
        return _denial(role_check)

    if user.role == "platform_admin" or policy.group_visibility_for_scope("usage:read") == "all":
        visible_groups = session.scalars(select(Group).order_by(Group.name.asc())).all()
    else:
        result = auth.authorize_scope(identity, "usage:read", user.primary_group_id)
        if not result.allowed:
            return _denial(result)
        visible_groups = [result.group]

    return [
        GroupResponse(group_id=group.group_id, name=group.name, team_lead_user_id=group.team_lead_user_id)
        for group in visible_groups
    ]


@router.get(
    "/usage/summary",
    response_model=UsageSummaryResponse,
    responses={403: {"model": DenialResponse}},
)
def usage_summary(
    period: str,
    group_id: str | None = None,
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
    policy: EnvironmentPolicy = Depends(get_policy),
):
    period_range = _period_or_422(period)
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)
    auth = get_authorization_service(session, policy)
    result = auth.authorize_scope(identity, "usage:read", group_id)
    if not result.allowed:
        return _denial(result)

    usage = get_usage_service(session)
    platforms = usage.platform_totals(result.group.group_id, period_range)
    return UsageSummaryResponse(
        group=result.group.group_id,
        period={"start": period_range.start, "end_exclusive": period_range.end_exclusive},
        platforms=[_platform_response(item) for item in platforms],
        totals=_totals_response(combined_totals(platforms)),
    )


@router.get(
    "/usage/by-week",
    response_model=list[WeeklyUsageResponse],
    responses={403: {"model": DenialResponse}},
)
def usage_by_week(
    group_id: str | None = None,
    platform: str | None = Query(default=None),
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
    policy: EnvironmentPolicy = Depends(get_policy),
):
    if platform is not None and platform not in PLATFORMS:
        raise HTTPException(status_code=422, detail="Unsupported platform.")
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)
    auth = get_authorization_service(session, policy)
    result = auth.authorize_scope(identity, "usage:read", group_id)
    if not result.allowed:
        return _denial(result)

    weeks = get_usage_service(session).weekly_totals(result.group.group_id, platform)
    return [
        WeeklyUsageResponse(
            week=item.week,
            start=item.start,
            end_exclusive=item.end_exclusive,
            platforms=[_platform_response(platform_item) for platform_item in item.platforms],
            totals=_totals_response(item.totals),
        )
        for item in weeks
    ]


@router.get(
    "/usage/top-users",
    response_model=list[TopUserResponse],
    responses={403: {"model": DenialResponse}},
)
def top_users(
    period: str,
    group_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=25),
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
    policy: EnvironmentPolicy = Depends(get_policy),
):
    period_range = _period_or_422(period)
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)
    auth = get_authorization_service(session, policy)
    result = auth.authorize_scope(identity, "usage:read", group_id)
    if not result.allowed:
        return _denial(result)

    users = get_usage_service(session).top_users(result.group.group_id, period_range, limit)
    return [
        TopUserResponse(
            user_id=user.user_id,
            name=user.name,
            email=user.email,
            group=user.group,
            total_tokens=user.total_tokens,
            cost_usd=_cost(user.cost_usd),
        )
        for user in users
    ]


@router.get(
    "/capabilities",
    response_model=list[CapabilityStateResponse],
    responses={403: {"model": DenialResponse}},
)
def capability_status(
    group_id: str | None = None,
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
    policy: EnvironmentPolicy = Depends(get_policy),
):
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)
    auth = get_authorization_service(session, policy)
    result = auth.authorize_scope(identity, "usage:read", group_id)
    if not result.allowed:
        return _denial(result)

    capabilities = get_capability_service(session, policy)
    return [_capability_response(state) for state in capabilities.list_group_states(result.group.group_id)]


@router.put(
    "/capabilities/{group_id}/{capability}",
    response_model=CapabilityStateResponse,
    responses={403: {"model": DenialResponse}},
)
def set_capability(
    group_id: str,
    capability: str,
    body: CapabilityUpdateRequest,
    x_user_id: UserIdHeader = None,
    x_user_email: UserEmailHeader = None,
    session: Session = Depends(get_db),
    policy: EnvironmentPolicy = Depends(get_policy),
):
    if capability not in CAPABILITIES:
        raise HTTPException(status_code=422, detail="Unsupported capability.")
    identity = _identity_or_denial(session, x_user_id, x_user_email)
    if isinstance(identity, AuthorizationResult):
        return _denial(identity)

    auth = get_authorization_service(session, policy)
    result = auth.authorize_capability_write(identity, group_id, capability)
    if not result.allowed:
        return _denial(result)

    capabilities: CapabilityService = get_capability_service(session, policy)
    state = capabilities.set_override(result.group.group_id, capability, body.enabled, result.user)
    session.commit()
    return _capability_response(state)
