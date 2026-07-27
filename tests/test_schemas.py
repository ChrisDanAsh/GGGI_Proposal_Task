# Schema tests (Module 8) - S-1 through S-19 from the architecture
# doc's test plan, §6.2. No database, no web server: these run in
# milliseconds and exercise ProposalCreate/ProposalUpdate/ProposalRead
# and format_errors() in complete isolation.

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db.models import Proposal
from app.schemas.proposal import ProposalCreate, ProposalRead, format_errors


def _valid_payload(**overrides: object) -> dict[str, object]:
    """A fully-populated, valid ProposalCreate payload; override fields as needed."""
    payload: dict[str, object] = {
        "project_name": "Solar Mini-Grid",
        "country": "KE",
        "category": "renewable_energy",
        "budget_usd": "50000",
        "start_date": "2026-09-01",
        "summary": "A pilot solar microgrid for a rural health clinic.",
    }
    payload.update(overrides)
    return payload


def _single_error(payload: dict[str, object]) -> tuple[str, str]:
    """Construct with `payload`, expect exactly one rejected field, and
    return (field name, message)."""
    with pytest.raises(ValidationError) as exc_info:
        ProposalCreate(**payload)
    errors = format_errors(exc_info.value)
    assert len(errors) == 1
    field = next(iter(errors))
    return field, errors[field]


# S-1 - a fully populated valid payload
def test_s1_valid_payload_constructs() -> None:
    proposal = ProposalCreate(**_valid_payload())
    assert isinstance(proposal.budget_usd, Decimal)
    assert proposal.budget_usd == Decimal("50000")
    assert isinstance(proposal.start_date, date)
    assert proposal.start_date == date(2026, 9, 1)


# S-2 [REQ] - empty project name
def test_s2_empty_project_name_rejected() -> None:
    field, message = _single_error(_valid_payload(project_name=""))
    assert field == "project_name"
    assert message == "Project name is required."


# S-3 - whitespace-only project name is rejected, not stored as blank
def test_s3_whitespace_only_project_name_rejected() -> None:
    field, message = _single_error(_valid_payload(project_name="   "))
    assert field == "project_name"
    assert message == "Project name is required."


# S-4 - project name over the 200-character limit
def test_s4_project_name_too_long_rejected() -> None:
    field, message = _single_error(_valid_payload(project_name="x" * 201))
    assert field == "project_name"
    assert message == "Project name must be 200 characters or fewer."


# S-5 [REQ] - negative budget
def test_s5_negative_budget_rejected() -> None:
    field, message = _single_error(_valid_payload(budget_usd="-5"))
    assert field == "budget_usd"
    assert message == "Estimated budget must be greater than zero."


# S-6 - zero budget is not positive
def test_s6_zero_budget_rejected() -> None:
    field, message = _single_error(_valid_payload(budget_usd="0"))
    assert field == "budget_usd"
    assert message == "Estimated budget must be greater than zero."


# S-7 - non-numeric budget
def test_s7_non_numeric_budget_rejected() -> None:
    field, message = _single_error(_valid_payload(budget_usd="banana"))
    assert field == "budget_usd"
    assert message == "Estimated budget must be a number."


# S-8 - empty budget must not raise an unhandled error
def test_s8_empty_budget_rejected_cleanly() -> None:
    field, message = _single_error(_valid_payload(budget_usd=""))
    assert field == "budget_usd"
    assert message == "Estimated budget must be a number."


# S-9 - thousands separator is accepted
def test_s9_budget_with_thousands_separator_accepted() -> None:
    proposal = ProposalCreate(**_valid_payload(budget_usd="250,000"))
    assert proposal.budget_usd == Decimal("250000")


# S-10 [REQ] - summary over 300 characters
def test_s10_summary_too_long_rejected() -> None:
    field, message = _single_error(_valid_payload(summary="x" * 301))
    assert field == "summary"
    assert message == "Project summary must be 300 characters or fewer."


# S-11 - exactly 300 characters is the inclusive boundary
def test_s11_summary_exactly_300_accepted() -> None:
    proposal = ProposalCreate(**_valid_payload(summary="x" * 300))
    assert len(proposal.summary) == 300


# S-12 - empty summary is accepted; the field is optional
def test_s12_empty_summary_accepted() -> None:
    proposal = ProposalCreate(**_valid_payload(summary=""))
    assert proposal.summary == ""


# S-12b - summary omitted entirely defaults to ""
def test_s12b_summary_omitted_defaults_to_empty() -> None:
    payload = _valid_payload()
    del payload["summary"]
    proposal = ProposalCreate(**payload)
    assert proposal.summary == ""


# S-12c - whitespace-only summary normalises to "", same as omitted
def test_s12c_whitespace_only_summary_normalises_to_empty() -> None:
    proposal = ProposalCreate(**_valid_payload(summary="   "))
    assert proposal.summary == ""


# S-13 - start_date="" means "not provided"
def test_s13_empty_start_date_accepted_as_none() -> None:
    proposal = ProposalCreate(**_valid_payload(start_date=""))
    assert proposal.start_date is None


# S-14 - start_date omitted entirely
def test_s14_start_date_omitted_accepted_as_none() -> None:
    payload = _valid_payload()
    del payload["start_date"]
    proposal = ProposalCreate(**payload)
    assert proposal.start_date is None


# S-15 - an unparseable start date is rejected with the date message
def test_s15_invalid_start_date_rejected() -> None:
    field, message = _single_error(_valid_payload(start_date="not-a-date"))
    assert field == "start_date"
    assert message == "Planned start date must be a valid date."


# S-16 - an unknown country code maps through the value_error key,
# not the generic fallback
def test_s16_unknown_country_rejected_with_specific_message() -> None:
    field, message = _single_error(_valid_payload(country="ZZ"))
    assert field == "country"
    assert message == "Select a target country from the list."


# S-16b - a plausible-looking ISO code that is not a GGGI member
def test_s16b_non_member_country_rejected() -> None:
    field, message = _single_error(_valid_payload(country="IN"))
    assert field == "country"
    assert message == "Select a target country from the list."


# S-16c - lowercase input is accepted and normalised
def test_s16c_lowercase_country_normalised() -> None:
    proposal = ProposalCreate(**_valid_payload(country="ke"))
    assert proposal.country == "KE"


# S-17 - a category outside the five fixed options
def test_s17_unknown_category_rejected() -> None:
    field, message = _single_error(_valid_payload(category="nuclear"))
    assert field == "category"
    assert message == "Select a climate technology category from the list."


# S-18 - three fields invalid at once produces exactly three keyed messages
def test_s18_multiple_invalid_fields_report_one_message_each() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ProposalCreate(
            **_valid_payload(
                project_name="",
                budget_usd="-5",
                country="ZZ",
            )
        )
    errors = format_errors(exc_info.value)
    assert set(errors) == {"project_name", "budget_usd", "country"}
    assert errors["project_name"] == "Project name is required."
    assert errors["budget_usd"] == "Estimated budget must be greater than zero."
    assert errors["country"] == "Select a target country from the list."


# S-19 - ProposalRead serialises an ORM object and omits internal fields
def test_s19_proposal_read_from_orm_object() -> None:
    orm_proposal = Proposal(
        id=uuid.uuid4(),
        project_name="Flood Risk Mapping Tool",
        country="ET",
        category="climate_risk_mapping",
        budget_usd=Decimal("75000.00"),
        start_date=None,
        summary="",
        owner_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        deleted_at=None,
    )
    read = ProposalRead.model_validate(orm_proposal)
    dumped = read.model_dump()
    assert "deleted_at" not in dumped
    assert "owner_id" not in dumped
    assert dumped["project_name"] == "Flood Risk Mapping Tool"
