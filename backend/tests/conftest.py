from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.database import Base, make_engine, make_session_factory
from app.ingest.loader import ingest_all


REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_KIT = REPO_ROOT / "starter-kit"


@pytest.fixture()
def session() -> Session:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory("sqlite:///:memory:")
    factory.configure(bind=engine)
    with factory() as db:
        yield db


@pytest.fixture()
def ingested_session(session: Session) -> Session:
    ingest_all(session, STARTER_KIT)
    session.commit()
    return session
