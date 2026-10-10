import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_WINDOW_END = "2026-09-28"


@dataclass(frozen=True)
class Settings:
    database_url: str
    environment: str
    starter_kit_path: Path


def get_settings() -> Settings:
    environment = os.getenv("MERIDIAN_ENV", "dev")
    return Settings(
        database_url=os.getenv("MERIDIAN_DATABASE_URL", "sqlite:///backend/meridian.db"),
        environment=environment,
        starter_kit_path=Path(os.getenv("MERIDIAN_STARTER_KIT", str(PROJECT_ROOT / "starter-kit"))),
    )


def environment_policy_path(settings: Settings) -> Path:
    return settings.starter_kit_path / "environments" / f"{settings.environment}.yaml"
