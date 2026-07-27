# Rules about proposals that are neither about the shape of a field
# (that's the schemas, Module 8) nor about how a row is stored (that's
# the repository, Module 7). "No two live proposals may share a name" is
# a rule about this application, and it needs a home that isn't tangled
# up with web code. Nothing in this file imports fastapi or sqlalchemy's
# query builders directly - it only calls the repository - which is what
# makes it testable in a fraction of a second with no web server at all.

from uuid import UUID, uuid4

from app.db.models import Proposal
from app.db.repository import ProposalRepository
from app.schemas.proposal import ProposalCreate, ProposalUpdate
from app.services.errors import DuplicateProposalError, ProposalNotFoundError


def create_proposal(
    data: ProposalCreate, repo: ProposalRepository
) -> Proposal:
    """Create a proposal, rejecting a name already in live use."""
    if repo.exists_with_name(data.project_name):
        raise DuplicateProposalError(data.project_name)
    proposal = Proposal(
        id=uuid4(),
        project_name=data.project_name,
        country=data.country,
        # category is a Category enum member on the validated schema, but
        # a plain string column on the model - .value unwraps it.
        # country needs no such unwrap: the schema already validated and
        # normalised it to a plain string.
        category=data.category.value,
        budget_usd=data.budget_usd,
        start_date=data.start_date,
        summary=data.summary,
    )
    return repo.add(proposal)


def get_proposal(proposal_id: UUID, repo: ProposalRepository) -> Proposal:
    """Fetch one live proposal or raise ProposalNotFoundError."""
    proposal = repo.get(proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(proposal_id)
    return proposal


def list_proposals(
    repo: ProposalRepository,
    country: str | None = None,
    category: str | None = None,
) -> list[Proposal]:
    """List live proposals, newest first, optionally filtered.

    A thin pass-through today, existing so every route depends on the
    service layer uniformly. When pagination or sorting is added, it
    changes here and no route needs to move.
    """
    return repo.list(country=country, category=category)


def update_proposal(
    proposal_id: UUID, data: ProposalUpdate, repo: ProposalRepository
) -> Proposal:
    """Edit a proposal, rejecting a name another live proposal uses."""
    # Fetched first so editing something already deleted (in another
    # browser tab, say) raises ProposalNotFoundError rather than running
    # the duplicate check against a proposal that no longer exists.
    proposal = get_proposal(proposal_id, repo)
    # exclude_id=proposal_id means saving the proposal without renaming
    # it is never reported as a duplicate of itself.
    if repo.exists_with_name(data.project_name, exclude_id=proposal_id):
        raise DuplicateProposalError(data.project_name)
    return repo.update(
        proposal,
        {
            "project_name": data.project_name,
            "country": data.country,
            "category": data.category.value,
            "budget_usd": data.budget_usd,
            "start_date": data.start_date,
            "summary": data.summary,
        },
    )


def delete_proposal(proposal_id: UUID, repo: ProposalRepository) -> None:
    """Soft-delete a proposal.

    Fetches before deleting, so deleting the same proposal twice - a
    double-clicked button, a re-submitted form - produces a clean
    ProposalNotFoundError on the second call rather than silently doing
    nothing.
    """
    proposal = get_proposal(proposal_id, repo)
    repo.soft_delete(proposal)
