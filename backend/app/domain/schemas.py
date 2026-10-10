from datetime import date
from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class UsageFactRead(BaseModel):
    platform: str
    usage_date: date
    user_id: str
    group_id: str
    model: str
    total_tokens: int
    cost_usd: float


class DenialResponse(BaseModel):
    error: str
    reason: str
    required_scope: str | None = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    group_id: str


class GroupResponse(BaseModel):
    group_id: str
    name: str
    team_lead_user_id: str


class PeriodResponse(BaseModel):
    start: date
    end_exclusive: date


class PlatformTotalsResponse(BaseModel):
    platform: str
    requests: int | None = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


class CombinedTotalsResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


class UsageSummaryResponse(BaseModel):
    group: str
    period: PeriodResponse
    platforms: list[PlatformTotalsResponse]
    totals: CombinedTotalsResponse


class WeeklyUsageResponse(BaseModel):
    week: str
    start: date
    end_exclusive: date
    platforms: list[PlatformTotalsResponse]
    totals: CombinedTotalsResponse


class TopUserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    group: str
    total_tokens: int
    cost_usd: float


class CapabilityStateResponse(BaseModel):
    group: str
    capability: str
    enabled: bool
    updated_at: datetime | None = None
    updated_by: str | None = None


class CapabilityUpdateRequest(BaseModel):
    enabled: bool
