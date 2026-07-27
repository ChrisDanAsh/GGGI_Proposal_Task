# Shared pytest fixtures. The full test suite (test_web_routes.py,
# test_api.py, test_constants.py) is Module 17 and lands with Phase 6;
# these fixtures are needed now so test_schemas.py and test_services.py
# (Modules 8 and 10) can run against a real, isolated database.

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.db.bootstrap import ensure_database_exists
from app.db.models import Base
from app.db.repository import ProposalRepository
from app.db.session import get_db
from app.main import app

# A dedicated test database, never the development one - the engine
# fixture below drops and recreates every table each session, which
# would destroy real data if pointed at the dev database. Overridable
# via TEST_DATABASE_URL so CI or another machine can point elsewhere.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ctaf:ctaf@localhost:5432/ctaf_test",
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Session-wide engine with the test database and schema created once."""
    # ensure_database_exists (Module 4) means pytest works against a
    # Postgres server that has never heard of ctaf_test - no createdb
    # step to forget, here or in a CI pipeline.
    ensure_database_exists(TEST_DATABASE_URL)
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    # create_all from the same Base.metadata that generated the Alembic
    # migration, not the migration itself - faster, and the migration
    # path is exercised separately by the Compose stack (Module 16).
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def connection(engine: Engine) -> Iterator[Connection]:
    conn = engine.connect()
    yield conn
    conn.close()


@pytest.fixture()
def db_session(connection: Connection) -> Iterator[Session]:
    """One test = one transaction, always rolled back.

    join_transaction_mode="create_savepoint" is what makes isolation
    work: get_db() commits through this session, and without this
    setting that commit would end the outer transaction, leaving the
    final rollback below nothing to undo and leaking rows into the next
    test. With it, commits land on savepoints inside this fixture's
    transaction, and the rollback discards everything regardless.
    """
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield session
    session.close()
    transaction.rollback()


@pytest.fixture()
def repo(db_session: Session) -> ProposalRepository:
    return ProposalRepository(db_session)


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient whose requests share the test's transaction.

    Overriding get_db (rather than swapping the engine) means the
    route, service, and repository code under test is byte-for-byte
    what runs in production - only where the session comes from
    differs. The override yields the very session this fixture manages,
    so writes made inside a request are visible to assertions made
    after it in the same test.
    """

    def _override_get_db() -> Iterator[Session]:
        yield db_session
        db_session.flush()

    app.dependency_overrides[get_db] = _override_get_db
    # Used as a context manager so startup/shutdown events fire as they
    # would in a real run.
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
