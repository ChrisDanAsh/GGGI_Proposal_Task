# Service tests (Module 10, exercising Module 9's exceptions too) - V-1
# through V-18 from the architecture doc's test plan, §6.3. These use a
# real Postgres database through the `repo` fixture, but never go
# through HTTP - proving the rules hold with no web server involved.

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Proposal
from app.db.repository import ProposalRepository
from app.schemas.proposal import ProposalCreate, ProposalUpdate
from app.services.errors import DuplicateProposalError, ProposalNotFoundError
from app.services.proposal import (
    create_proposal,
    delete_proposal,
    get_proposal,
    list_proposals,
    update_proposal,
)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "project_name": "Solar Mini-Grid",
        "country": "KE",
        "category": "renewable_energy",
        "budget_usd": "50000",
        "start_date": None,
        "summary": "",
    }
    payload.update(overrides)
    return payload


def _create(repo: ProposalRepository, **overrides: object) -> Proposal:
    return create_proposal(ProposalCreate(**_payload(**overrides)), repo)


def _stagger_created_at(repo: ProposalRepository, proposal: Proposal, when: datetime) -> None:
    """Force a specific created_at for ordering tests.

    All creates inside one test share a single Postgres transaction, and
    Postgres's now() (what the model's server_default uses) is fixed for
    the whole transaction - not the statement - so rows created back to
    back in the same test would otherwise carry an identical timestamp.
    Overwriting created_at directly is the one place a test reaches past
    the service layer, purely to make ordering assertions deterministic;
    real chronological ordering across separate requests (separate
    transactions) was already confirmed manually for Module 7.
    """
    proposal.created_at = when
    repo.db.flush()


# V-1 [REQ] - creating with valid data
def test_v1_create_proposal_succeeds(repo: ProposalRepository) -> None:
    proposal = _create(repo)
    assert proposal.id is not None
    assert proposal.created_at is not None
    assert proposal.deleted_at is None
    assert proposal in repo.list()


# V-2 - duplicate name is rejected, and the exception carries the name
def test_v2_duplicate_name_rejected(repo: ProposalRepository) -> None:
    _create(repo, project_name="Solar Mini-Grid")
    with pytest.raises(DuplicateProposalError) as exc_info:
        _create(repo, project_name="Solar Mini-Grid")
    assert exc_info.value.project_name == "Solar Mini-Grid"


# V-3 - duplicate check is case-insensitive
def test_v3_duplicate_name_case_insensitive(repo: ProposalRepository) -> None:
    _create(repo, project_name="Solar Grid")
    with pytest.raises(DuplicateProposalError):
        _create(repo, project_name="solar grid")


# V-4 - the uniqueness rule constrains live proposals only
def test_v4_name_reusable_after_delete(repo: ProposalRepository) -> None:
    first = _create(repo, project_name="Battery Storage Pilot")
    delete_proposal(first.id, repo)
    # Must not raise - the original holder of the name is no longer live.
    second = _create(repo, project_name="Battery Storage Pilot")
    assert second.id != first.id


# V-5 - an unknown id raises ProposalNotFoundError
def test_v5_get_unknown_id_raises_not_found(repo: ProposalRepository) -> None:
    with pytest.raises(ProposalNotFoundError):
        get_proposal(uuid4(), repo)


# V-6 - a soft-deleted proposal is not found either
def test_v6_get_deleted_proposal_raises_not_found(repo: ProposalRepository) -> None:
    proposal = _create(repo)
    delete_proposal(proposal.id, repo)
    with pytest.raises(ProposalNotFoundError):
        get_proposal(proposal.id, repo)


# V-7 [REQ] - filtering by country returns only that country's rows
def test_v7_filter_by_country(repo: ProposalRepository) -> None:
    ke1 = _create(repo, project_name="KE Project One", country="KE")
    ke2 = _create(repo, project_name="KE Project Two", country="KE")
    _create(repo, project_name="ET Project", country="ET")

    results = list_proposals(repo, country="KE")
    assert {p.id for p in results} == {ke1.id, ke2.id}


# V-8 - filtering by category
def test_v8_filter_by_category(repo: ProposalRepository) -> None:
    smart_grid = _create(
        repo, project_name="Grid Sensors", category="smart_grid"
    )
    _create(repo, project_name="Solar Farm", category="renewable_energy")

    results = list_proposals(repo, category="smart_grid")
    assert [p.id for p in results] == [smart_grid.id]


# V-9 - both filters applied together
def test_v9_filter_by_country_and_category(repo: ProposalRepository) -> None:
    match = _create(
        repo,
        project_name="KE Smart Grid",
        country="KE",
        category="smart_grid",
    )
    _create(repo, project_name="KE Solar", country="KE", category="renewable_energy")
    _create(repo, project_name="ET Smart Grid", country="ET", category="smart_grid")

    results = list_proposals(repo, country="KE", category="smart_grid")
    assert [p.id for p in results] == [match.id]


# V-10 - a filter matching nothing returns an empty list, not an error
def test_v10_filter_matching_nothing_returns_empty(repo: ProposalRepository) -> None:
    _create(repo, project_name="KE Project", country="KE")
    assert list_proposals(repo, country="VN") == []


# V-11 - no filters returns every live proposal, newest first
def test_v11_list_all_newest_first(repo: ProposalRepository) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    oldest = _create(repo, project_name="Oldest")
    _stagger_created_at(repo, oldest, base)
    middle = _create(repo, project_name="Middle")
    _stagger_created_at(repo, middle, base + timedelta(hours=1))
    newest = _create(repo, project_name="Newest")
    _stagger_created_at(repo, newest, base + timedelta(hours=2))

    results = list_proposals(repo)
    assert [p.id for p in results] == [newest.id, middle.id, oldest.id]


# V-12 [REQ] - deleting removes the proposal from the list
def test_v12_delete_removes_from_list(repo: ProposalRepository) -> None:
    proposal = _create(repo)
    delete_proposal(proposal.id, repo)
    assert proposal.id not in [p.id for p in list_proposals(repo)]


# V-13 - the delete is soft: the row still exists with deleted_at set
def test_v13_delete_is_soft(repo: ProposalRepository) -> None:
    proposal = _create(repo)
    delete_proposal(proposal.id, repo)

    # Bypasses the repository's own deleted_at filter deliberately, to
    # verify the row itself was never removed from the table.
    row = repo.db.scalars(
        select(Proposal).where(Proposal.id == proposal.id)
    ).one()
    assert row.deleted_at is not None


# V-14 - deleting twice raises on the second call
def test_v14_delete_twice_raises_on_second_call(repo: ProposalRepository) -> None:
    proposal = _create(repo)
    delete_proposal(proposal.id, repo)
    with pytest.raises(ProposalNotFoundError):
        delete_proposal(proposal.id, repo)


# V-15 - updating changes the edited fields but not identity
def test_v15_update_changes_fields_keeps_identity(repo: ProposalRepository) -> None:
    proposal = _create(repo, budget_usd="10000", summary="Original summary.")
    original_id = proposal.id
    original_created_at = proposal.created_at

    updated = update_proposal(
        proposal.id,
        ProposalUpdate(**_payload(budget_usd="20000", summary="Revised summary.")),
        repo,
    )

    assert updated.budget_usd == 20000
    assert updated.summary == "Revised summary."
    assert updated.id == original_id
    assert updated.created_at == original_created_at
    # Within a single test's shared transaction, Postgres's now() (used
    # by both created_at's server_default and updated_at's onupdate) is
    # frozen for the whole transaction, so the two can legitimately be
    # equal here even though the UPDATE genuinely ran. The assertion
    # below is what always holds; real clock advancement across
    # separate requests was confirmed manually when Module 7 was built.
    assert updated.updated_at >= original_created_at


# V-16 - saving without renaming is not a duplicate of itself
def test_v16_update_keeping_same_name_succeeds(repo: ProposalRepository) -> None:
    proposal = _create(repo, project_name="Unchanged Name")
    updated = update_proposal(
        proposal.id,
        ProposalUpdate(**_payload(project_name="Unchanged Name", budget_usd="99999")),
        repo,
    )
    assert updated.project_name == "Unchanged Name"
    assert updated.budget_usd == 99999


# V-17 - renaming to another live proposal's name is rejected
def test_v17_update_to_another_live_name_rejected(repo: ProposalRepository) -> None:
    _create(repo, project_name="Taken Name")
    other = _create(repo, project_name="Original Name")

    with pytest.raises(DuplicateProposalError):
        update_proposal(
            other.id,
            ProposalUpdate(**_payload(project_name="Taken Name")),
            repo,
        )


# V-18 - editing a deleted proposal raises ProposalNotFoundError
def test_v18_update_deleted_proposal_raises_not_found(repo: ProposalRepository) -> None:
    proposal = _create(repo)
    delete_proposal(proposal.id, repo)
    with pytest.raises(ProposalNotFoundError):
        update_proposal(
            proposal.id,
            ProposalUpdate(**_payload(project_name="New Name")),
            repo,
        )
