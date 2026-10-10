import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


def stable_key(parts: list[Any]) -> str:
    raw = "\x1f".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_rfc3339_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(timezone.utc)


def parse_bigquery_utc(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S %Z")
    return parsed.replace(tzinfo=timezone.utc)


def usage_date_from_rfc3339(value: str) -> date:
    return parse_rfc3339_utc(value).date()


def usage_date_from_bigquery(value: str) -> date:
    return parse_bigquery_utc(value).date()


def decimal_from_json_number(value: Any) -> Decimal:
    return Decimal(str(value))


def cents_to_usd(value: str) -> Decimal:
    return Decimal(value) / Decimal("100")


def labels_to_dict(labels: list[dict[str, str]]) -> dict[str, str]:
    return {item["key"]: item["value"] for item in labels}
