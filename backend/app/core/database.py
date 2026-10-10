from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(database_url), autoflush=False, expire_on_commit=False)


def create_all(database_url: str) -> None:
    from app.domain import models  # noqa: F401

    engine = make_engine(database_url)
    Base.metadata.create_all(engine)


def session_scope(database_url: str) -> Generator[Session, None, None]:
    factory = make_session_factory(database_url)
    with factory() as session:
        yield session
