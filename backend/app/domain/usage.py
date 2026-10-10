from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Group, UsageFact, User
from app.domain.periods import PeriodRange, iso_week_start


PLATFORMS = {"claude", "gemini"}
MONEY_QUANT = Decimal("0.000001")


def money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PlatformTotals:
    platform: str
    requests: int | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal


@dataclass(frozen=True)
class UserTotals:
    user_id: str
    name: str
    email: str
    group: str
    total_tokens: int
    cost_usd: Decimal


@dataclass(frozen=True)
class WeeklyTotals:
    week: str
    start: str
    end_exclusive: str
    platforms: list[PlatformTotals]
    totals: dict[str, int | Decimal]


class UsageService:
    def __init__(self, session: Session):
        self.session = session

    def platform_totals(self, group_id: str, period: PeriodRange) -> list[PlatformTotals]:
        rows = self.session.execute(
            select(
                UsageFact.platform,
                func.sum(UsageFact.requests),
                func.sum(UsageFact.input_tokens),
                func.sum(UsageFact.output_tokens),
                func.sum(UsageFact.total_tokens),
                func.sum(UsageFact.cost_usd),
            )
            .where(
                UsageFact.group_id == group_id,
                UsageFact.usage_date >= period.start,
                UsageFact.usage_date < period.end_exclusive,
            )
            .group_by(UsageFact.platform)
        ).all()
        by_platform = {
            row[0]: PlatformTotals(
                platform=row[0],
                requests=None if row[0] == "gemini" else int(row[1] or 0),
                input_tokens=int(row[2] or 0),
                output_tokens=int(row[3] or 0),
                total_tokens=int(row[4] or 0),
                cost_usd=money(row[5]),
            )
            for row in rows
        }
        return [
            by_platform.get(platform)
            or PlatformTotals(platform, None if platform == "gemini" else 0, 0, 0, 0, Decimal("0.000000"))
            for platform in ("claude", "gemini")
        ]

    def top_users(self, group_id: str, period: PeriodRange, limit: int) -> list[UserTotals]:
        rows = self.session.execute(
            select(
                User.user_id,
                User.name,
                User.email,
                Group.name,
                func.sum(UsageFact.total_tokens).label("total_tokens"),
                func.sum(UsageFact.cost_usd).label("cost_usd"),
            )
            .join(User, User.user_id == UsageFact.user_id)
            .join(Group, Group.group_id == UsageFact.group_id)
            .where(
                UsageFact.group_id == group_id,
                UsageFact.usage_date >= period.start,
                UsageFact.usage_date < period.end_exclusive,
            )
            .group_by(User.user_id, User.name, User.email, Group.name)
            .order_by(func.sum(UsageFact.total_tokens).desc(), User.name.asc(), User.user_id.asc())
            .limit(limit)
        ).all()
        return [
            UserTotals(
                user_id=row.user_id,
                name=row.name,
                email=row.email,
                group=row.name_1,
                total_tokens=int(row.total_tokens or 0),
                cost_usd=money(row.cost_usd),
            )
            for row in rows
        ]

    def weekly_totals(self, group_id: str, platform: str | None = None) -> list[WeeklyTotals]:
        if platform is not None and platform not in PLATFORMS:
            raise ValueError("Unsupported platform.")

        where_clauses = [UsageFact.group_id == group_id]
        if platform is not None:
            where_clauses.append(UsageFact.platform == platform)

        rows = self.session.execute(
            select(
                UsageFact.usage_date,
                UsageFact.platform,
                func.sum(UsageFact.requests),
                func.sum(UsageFact.input_tokens),
                func.sum(UsageFact.output_tokens),
                func.sum(UsageFact.total_tokens),
                func.sum(UsageFact.cost_usd),
            )
            .where(*where_clauses)
            .group_by(UsageFact.usage_date, UsageFact.platform)
            .order_by(UsageFact.usage_date.asc(), UsageFact.platform.asc())
        ).all()

        buckets: dict = {}
        for row in rows:
            start = iso_week_start(row.usage_date)
            week = f"{start.isocalendar().year}-W{start.isocalendar().week:02d}"
            bucket = buckets.setdefault(
                start,
                {
                    "week": week,
                    "start": start.isoformat(),
                    "end_exclusive": (start + timedelta(days=7)).isoformat(),
                    "platforms": {},
                },
            )
            current = bucket["platforms"].get(row.platform)
            addition = PlatformTotals(
                platform=row.platform,
                requests=None if row.platform == "gemini" else int(row[2] or 0),
                input_tokens=int(row[3] or 0),
                output_tokens=int(row[4] or 0),
                total_tokens=int(row[5] or 0),
                cost_usd=money(row[6]),
            )
            if current is None:
                bucket["platforms"][row.platform] = addition
            else:
                bucket["platforms"][row.platform] = PlatformTotals(
                    platform=row.platform,
                    requests=None if row.platform == "gemini" else int(current.requests or 0) + int(addition.requests or 0),
                    input_tokens=current.input_tokens + addition.input_tokens,
                    output_tokens=current.output_tokens + addition.output_tokens,
                    total_tokens=current.total_tokens + addition.total_tokens,
                    cost_usd=money(current.cost_usd + addition.cost_usd),
                )

        results = []
        platforms = (platform,) if platform else ("claude", "gemini")
        for start in sorted(buckets):
            bucket = buckets[start]
            platform_totals = [
                bucket["platforms"].get(name)
                or PlatformTotals(name, None if name == "gemini" else 0, 0, 0, 0, Decimal("0.000000"))
                for name in platforms
            ]
            results.append(
                WeeklyTotals(
                    week=bucket["week"],
                    start=bucket["start"],
                    end_exclusive=bucket["end_exclusive"],
                    platforms=platform_totals,
                    totals={
                        "total_tokens": sum(item.total_tokens for item in platform_totals),
                        "cost_usd": money(sum((item.cost_usd for item in platform_totals), Decimal("0"))),
                    },
                )
            )
        return results


def combined_totals(platforms: list[PlatformTotals]) -> dict[str, int | Decimal]:
    return {
        "input_tokens": sum(item.input_tokens for item in platforms),
        "output_tokens": sum(item.output_tokens for item in platforms),
        "total_tokens": sum(item.total_tokens for item in platforms),
        "cost_usd": money(sum((item.cost_usd for item in platforms), Decimal("0"))),
    }
