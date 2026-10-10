from app.main import health


def test_health():
    assert health().model_dump() == {"status": "ok"}
