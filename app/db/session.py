from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# The engine manages the pool of physical connections to Postgres. Building
# it here, at import time, does not itself open a connection — connections
# are opened lazily on first use — so importing this module never requires
# a reachable database.
engine = create_engine(
    get_settings().database_url,
    # Runs a trivial "is this connection still alive" check before handing
    # a pooled connection to a request. Without this, the first request
    # after Postgres restarts (e.g. `docker compose restart`) would fail
    # with a stale-connection error instead of silently reconnecting.
    pool_pre_ping=True,
    future=True,
)

# A factory that produces new Session objects, all sharing the engine above.
SessionLocal = sessionmaker(
    bind=engine,
    # Writes are only sent to the database when explicitly flushed or
    # committed, never as a side effect of a query — so the repository
    # controls exactly when a write happens.
    autoflush=False,
    autocommit=False,
    # By default SQLAlchemy marks every loaded attribute "stale" the
    # instant a transaction commits, so reading it afterwards re-queries
    # the database — and raises if the session is already closed. Because
    # get_db() commits *after* the route has already built its response
    # (e.g. for a template to render), that default would break every
    # request. Disabling expiry keeps already-loaded values readable.
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """Yield one database session per request.

    Commits when the request handler returns normally, rolls back if
    it raised, and always closes the connection. FastAPI's `Depends(get_db)`
    runs this as a generator: the code before `yield` runs before the route,
    and the code after `yield` runs after the route returns, so a route
    never has to open, commit, or close a session itself.
    """
    db = SessionLocal()
    try:
        # Hand the session to the route. Everything the route does with
        # `db` (querying, adding objects) happens here, "inside" this yield.
        yield db
        # Only reached if the route ran to completion without raising -
        # make every write from this request permanent as one transaction.
        db.commit()
    except Exception:
        # The route (or something it called) raised. Undo any partial
        # writes from this request so a half-saved proposal can never
        # exist, then re-raise so FastAPI's error handling still runs.
        db.rollback()
        raise
    finally:
        # Always return the connection to the pool, whether the request
        # succeeded or failed.
        db.close()
