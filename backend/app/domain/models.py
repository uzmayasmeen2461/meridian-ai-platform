from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    primary_group_id: Mapped[str] = mapped_column(ForeignKey("groups.group_id"), nullable=False)
    claude_seat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gcp_principal: Mapped[str] = mapped_column(String, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="users", foreign_keys=[primary_group_id])


class Group(Base):
    __tablename__ = "groups"

    group_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    team_lead_user_id: Mapped[str] = mapped_column(String, nullable=False)
    claude_rbac_group_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    gcp_project_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    gcp_project_number: Mapped[str] = mapped_column(String, nullable=False)
    cost_centre: Mapped[str] = mapped_column(String, nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="group", foreign_keys=[User.primary_group_id])


class UsageFact(Base):
    __tablename__ = "usage_facts"
    __table_args__ = (
        UniqueConstraint("platform", "source_key", name="uq_usage_facts_platform_source_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String, nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.group_id"), nullable=False, index=True)

    model: Mapped[str] = mapped_column(String, nullable=False)
    product: Mapped[str | None] = mapped_column(String, nullable=True)
    source_dimension: Mapped[str | None] = mapped_column(String, nullable=True)

    uncached_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_creation_5m_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_creation_1h_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    web_search_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    token_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=Decimal("0"), nullable=False)
    web_search_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=Decimal("0"), nullable=False)
    input_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=Decimal("0"), nullable=False)
    output_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=Decimal("0"), nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=Decimal("0"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class CapabilityOverride(Base):
    __tablename__ = "capability_overrides"
    __table_args__ = (
        UniqueConstraint("group_id", "capability", name="uq_capability_overrides_group_capability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.group_id"), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
