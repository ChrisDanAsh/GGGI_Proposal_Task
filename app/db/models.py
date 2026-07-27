# The proposals table, expressed as a Python class rather than raw SQL.
# SQLAlchemy reads this class to generate the SQL for every query in the
# repository (Module 7) and Alembic (Module 6) reads it to generate
# migrations. Two things follow from describing the table this way instead
# of writing SQL by hand: the editor catches a misspelled column name
# before the code ever runs, and every value is sent to Postgres as a
# bound parameter rather than spliced into a query string - which makes
# SQL injection (e.g. typing `'; DROP TABLE proposals; --` into the
# project name field) structurally impossible rather than something to
# remember to defend against.

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base; Alembic reads Base.metadata to autogenerate."""


class Proposal(Base):
    """One climate technology project proposal."""

    __tablename__ = "proposals"

    # A random UUID rather than an auto-incrementing integer. Sequential
    # integers in a URL (/proposals/17) disclose how many proposals exist
    # and invite guessing at neighbouring records; a UUID does not.
    # Generated in Python (default=uuid.uuid4), not by the database, so the
    # id is already known before the row is written.
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Bounded at 200 to match the schema's max_length=200 (Module 8) - a
    # length enforced by the database survives a bug in the application
    # layer that might otherwise let a longer value through.
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # The ISO 3166-1 alpha-2 code (e.g. "KE"), not the display name, so the
    # wording shown to a person can change without touching stored data.
    # Indexed because every list/filter query filters on it.
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    # Stored as a plain string rather than a native Postgres ENUM type.
    # A native enum needs an ALTER TYPE migration every time a category is
    # added; a string column plus the Pydantic enum (Module 8) gives the
    # same validation guarantee without that friction. Indexed for the
    # same reason as country.
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Money is never a float: binary floating point stores 0.1
    # approximately, and the error compounds across arithmetic. NUMERIC
    # stores the exact decimal value. 15 digits with 2 after the point
    # allows up to 9,999,999,999,999.99, far beyond any plausible budget.
    budget_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    # Nullable because the assignment does not mark a start date required.
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Unbounded at the database on purpose - the 300-character limit from
    # the assignment is a rule of the application, enforced by the schema
    # (Module 8), not a storage constraint. An absent summary is stored as
    # "" rather than NULL, so there is exactly one representation of
    # "no summary" instead of two ways to mean the same thing.
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Empty for every row today - there are no user accounts. Reserved
    # against a future with accounts: if that column were added later
    # there would be no way to work out who created rows already saved.
    # Adding it now, nullable, costs nothing and keeps that door open.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    # server_default=func.now() means Postgres stamps this, not the
    # application, so the value can never drift with an app server's clock.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # onupdate=func.now() makes SQLAlchemy re-stamp this on every UPDATE
    # this application issues (e.g. editing a proposal).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # NULL means the proposal is live. Deleting sets this to the current
    # time instead of removing the row (a "soft delete"), so an accidental
    # deletion is recoverable and there is a record of what happened.
    # Indexed because *every single read* in the repository filters on it.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return f"<Proposal {self.id} {self.project_name!r}>"
