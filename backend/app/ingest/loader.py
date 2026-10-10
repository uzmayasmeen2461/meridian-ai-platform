from pathlib import Path

from sqlalchemy.orm import Session

from app.ingest.claude import ingest_claude
from app.ingest.directory import load_directory
from app.ingest.gemini import ingest_gemini


def ingest_all(session: Session, starter_kit: Path) -> None:
    load_directory(session, starter_kit)
    session.flush()
    ingest_claude(session, starter_kit)
    ingest_gemini(session, starter_kit)
