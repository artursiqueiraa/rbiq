import pytest
from sqlalchemy import text

from app.database.session import SessionLocal

# Tests under tests/data/integration/ need a real PostgreSQL — that's the point of
# this directory. Everything here uses a symbol under this prefix so teardown can
# be one blanket DELETE without ever touching data a human imported for real.
TEST_SYMBOL_PREFIX = "TEST_"


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_test_data():
    yield
    session = SessionLocal()
    try:
        session.execute(text("DELETE FROM candles WHERE symbol LIKE :prefix"), {"prefix": f"{TEST_SYMBOL_PREFIX}%"})
        session.execute(text("DELETE FROM data_imports WHERE symbol LIKE :prefix"), {"prefix": f"{TEST_SYMBOL_PREFIX}%"})
        session.commit()
    finally:
        session.close()
