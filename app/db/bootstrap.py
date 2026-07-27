import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)


def ensure_database_exists(database_url: str) -> bool:
    """Create the target database if the server does not already have it.

    `alembic upgrade head` (Module 6) creates *tables* inside a database,
    but it has to connect to that database before it can do anything - it
    cannot create the database itself. Normally a person runs `createdb`
    by hand first. This function closes that gap in code instead, so a
    bare Postgres server needs no manual preparation.

    Connects to the server's default `postgres` maintenance database
    (every Postgres server has one, so it is always safe to connect to),
    checks pg_catalog for the target database, and issues CREATE DATABASE
    only when it is absent.

    Returns True if a database was created, False if it already existed.
    Raises if the server itself is unreachable — that is a real problem
    and must not be swallowed, as opposed to a missing *database*, which
    this function is expected to fix.
    """
    url = make_url(database_url)
    target = url.database
    if not target:
        raise ValueError(f"No database name in URL: {database_url}")

    # Swap in "postgres" as the database to connect to, keeping the same
    # host, port, and credentials as the real target.
    admin_url = url.set(database="postgres")
    # AUTOCOMMIT is required, not stylistic: Postgres refuses to run
    # CREATE DATABASE inside a transaction block, and SQLAlchemy opens one
    # by default.
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            # Check first rather than attempting CREATE DATABASE and
            # catching "already exists" - this keeps a normal startup free
            # of errors in the log, and lets the return value say which
            # case happened.
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target},
            )
            if exists:
                return False
            # The database name is interpolated directly into the SQL
            # string rather than passed as a bound parameter, because
            # Postgres does not accept a parameter in this position. This
            # is safe only because `target` comes from the application's
            # own configuration (Module 1), never from user input - it is
            # the one deliberate exception to "never build SQL by string
            # concatenation" in this codebase.
            connection.execute(text(f'CREATE DATABASE "{target}"'))
            logger.info("Created database %s", target)
            return True
    finally:
        # Dispose of the admin engine's connection pool; it was only ever
        # needed for this one check-and-create.
        admin_engine.dispose()
