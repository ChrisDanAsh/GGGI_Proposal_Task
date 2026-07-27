# Every database query in the application lives in this one class. If
# queries were scattered across routes and services, changing anything
# about how proposals are stored would mean hunting through the whole
# codebase. Keeping them here also makes the soft-delete rule verifiable:
# "every read filters deleted_at IS NULL" is a claim that can be checked
# by reading this single file.

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Proposal


class ProposalRepository:
    """Every query against the proposals table.

    All reads exclude soft-deleted rows. Methods flush but never
    commit; the transaction is owned by get_db().
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, proposal: Proposal) -> Proposal:
        """Insert a proposal and return it with database defaults populated."""
        self.db.add(proposal)
        # flush() sends the INSERT immediately (without ending the
        # transaction) so Postgres computes created_at/updated_at; refresh()
        # then reads those computed values back onto the Python object.
        # commit() is never called here - one HTTP request is one
        # transaction, and that transaction is owned by get_db().
        self.db.flush()
        self.db.refresh(proposal)
        return proposal

    def get(self, proposal_id: UUID) -> Proposal | None:
        """Fetch one live proposal, or None if absent or deleted."""
        stmt = select(Proposal).where(
            Proposal.id == proposal_id,
            Proposal.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).one_or_none()

    def list(
        self,
        country: str | None = None,
        category: str | None = None,
    ) -> list[Proposal]:
        """List live proposals, newest first, optionally filtered."""
        stmt = select(Proposal).where(Proposal.deleted_at.is_(None))
        # Conditions are only added when a filter value is actually
        # present, so Postgres does the filtering using the country/
        # category indexes, rather than every row being loaded into
        # Python and filtered there.
        if country:
            stmt = stmt.where(Proposal.country == country)
        if category:
            stmt = stmt.where(Proposal.category == category)
        # func.lower(project_name) is the tie-break: several seeded rows
        # can share created_at down to microsecond precision (Postgres's
        # now() is fixed for the whole transaction, not per row), and a
        # UUID-based tie-break would make same-instant rows appear in an
        # arbitrary order. Sorting the tie-break alphabetically instead
        # means same-instant rows land in a human-meaningful order; the
        # lower() call matches exists_with_name's own case-insensitive
        # comparison so "apple" and "Banana" interleave as expected.
        stmt = stmt.order_by(
            Proposal.created_at.desc(), func.lower(Proposal.project_name).asc()
        )
        return list(self.db.scalars(stmt))

    def exists_with_name(
        self,
        project_name: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Whether a live proposal already uses this name, case-insensitively."""
        # func.lower(...) on both sides makes the comparison case-
        # insensitive ("Solar Mini-Grid" and "solar mini-grid" count as
        # the same name), and .strip() matches the schema's own
        # stripping so trailing whitespace can't be used to sneak past
        # the rule. This counts rather than fetching the row, since only
        # a yes/no answer is needed.
        stmt = select(func.count()).select_from(Proposal).where(
            func.lower(Proposal.project_name) == project_name.strip().lower(),
            Proposal.deleted_at.is_(None),
        )
        # exclude_id lets an edit exclude the proposal being edited from
        # this check - saving a proposal without renaming it must not
        # report it as a duplicate of itself.
        if exclude_id is not None:
            stmt = stmt.where(Proposal.id != exclude_id)
        return bool(self.db.scalar(stmt))

    def update(self, proposal: Proposal, fields: dict[str, Any]) -> Proposal:
        """Apply changed fields to a proposal already attached to the session."""
        # `fields` is a plain dict (typically from a schema's
        # model_dump()) rather than **kwargs, so a data key can never
        # collide with a parameter name.
        for name, value in fields.items():
            setattr(proposal, name, value)
        self.db.flush()
        self.db.refresh(proposal)
        return proposal

    def soft_delete(self, proposal: Proposal) -> None:
        """Mark a proposal deleted without removing the row."""
        # Setting deleted_at rather than issuing a SQL DELETE is what
        # makes an accidental deletion recoverable: the row stays on
        # disk, and every read above simply stops seeing it. There is no
        # hard_delete method - nothing in the application removes a row;
        # purging is an administrative act, out of scope here (see §7 of
        # the architecture doc).
        proposal.deleted_at = datetime.now(timezone.utc)
        self.db.flush()
