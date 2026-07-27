# The seven HTML routes. Each one does three things and stops: take the
# input, call exactly one service function, and return a page or a
# redirect. Nothing here queries the database directly and nothing here
# holds a business rule - that split is what makes the service layer
# (app/services/proposal.py) testable without a browser, and what makes
# this file short enough to read in one sitting.

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Proposal
from app.db.repository import ProposalRepository
from app.db.session import get_db
from app.domain.constants import Category, country_codes
from app.schemas.proposal import ProposalCreate, ProposalUpdate, format_errors
from app.services.errors import DuplicateProposalError, ProposalNotFoundError
from app.services.proposal import (
    create_proposal,
    delete_proposal,
    get_proposal,
    list_proposals,
    update_proposal,
)
from app.web.templates import templates

# Excluded from the generated API documentation at /docs, which
# describes the JSON API (Module 14) - these routes return HTML, not a
# documented request/response schema.
router = APIRouter(tags=["proposals"], include_in_schema=False)


def _form_context(
    *,
    mode: str,
    action: str,
    values: dict[str, str],
    errors: dict[str, str] | None = None,
    proposal: Proposal | None = None,
) -> dict[str, object]:
    """Build form.html's context, so the three call sites that re-render
    a form after a failed submission cannot drift apart from each other."""
    return {
        "mode": mode,
        "action": action,
        "values": values,
        "errors": errors or {},
        "proposal": proposal,
    }


def _raw_form(
    project_name: str,
    country: str,
    category: str,
    budget_usd: str,
    start_date: str,
    summary: str,
) -> dict[str, str]:
    """Collect the six posted fields into one dict - create and edit post
    identical fields, so both routes build this the same way."""
    return {
        "project_name": project_name,
        "country": country,
        "category": category,
        "budget_usd": budget_usd,
        "start_date": start_date,
        "summary": summary,
    }


def _values_from(proposal: Proposal) -> dict[str, str]:
    """Convert a stored proposal into the string dict form.html expects,
    for pre-filling the edit form."""
    return {
        "project_name": proposal.project_name,
        "country": proposal.country,
        "category": proposal.category,
        "budget_usd": f"{proposal.budget_usd:.2f}",
        "start_date": proposal.start_date.isoformat() if proposal.start_date else "",
        "summary": proposal.summary,
    }


# Declared before GET /proposals/{proposal_id}: FastAPI matches routes in
# declaration order, and with the dynamic route first the literal string
# "new" would be parsed as a UUID path parameter and produce a 422
# instead of the empty form.
@router.get("/proposals/new")
def new_proposal_form(request: Request) -> object:
    """Show the empty submission form."""
    return templates.TemplateResponse(
        request=request,
        name="form.html",
        context=_form_context(mode="create", action="/proposals", values={}),
    )


@router.get("/proposals")
def list_proposals_page(
    request: Request,
    country: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> object:
    """Show every live proposal, optionally filtered by country and/or category.

    A value outside either vocabulary is treated as absent rather than
    rejected - a hand-edited URL like ?country=ZZ degrades to the
    unfiltered list instead of an error page, which is the friendlier
    behaviour for something a person can type into an address bar. The
    JSON API (Module 14) takes the opposite position for the same
    situation, because a program passing a bad code has a bug and
    should be told.
    """
    if country is not None:
        country = country.strip().upper()
        if country not in country_codes():
            country = None
    if category is not None:
        try:
            category = Category(category).value
        except ValueError:
            category = None

    proposals = list_proposals(
        ProposalRepository(db), country=country, category=category
    )
    return templates.TemplateResponse(
        request=request,
        name="list.html",
        context={
            "proposals": proposals,
            "selected_country": country,
            "selected_category": category,
        },
    )


@router.post("/proposals")
def create_proposal_submit(
    request: Request,
    # Typed as plain str with "" defaults, never Optional[...] or
    # Decimal: if FastAPI coerced the budget itself, a non-numeric value
    # would produce FastAPI's own 422 JSON error page and the person
    # would lose everything they had typed. Accepting raw strings routes
    # every failure through format_errors instead, so the form always
    # re-renders with a message and the values already entered.
    project_name: str = Form(""),
    country: str = Form(""),
    category: str = Form(""),
    budget_usd: str = Form(""),
    start_date: str = Form(""),
    summary: str = Form(""),
    db: Session = Depends(get_db),
) -> object:
    """Validate a submitted proposal and create it, or re-render the form."""
    raw = _raw_form(project_name, country, category, budget_usd, start_date, summary)

    try:
        data = ProposalCreate(**raw)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request=request,
            name="form.html",
            context=_form_context(
                mode="create",
                action="/proposals",
                values=raw,
                errors=format_errors(exc),
            ),
            status_code=400,
        )

    try:
        create_proposal(data, ProposalRepository(db))
    except DuplicateProposalError as exc:
        return templates.TemplateResponse(
            request=request,
            name="form.html",
            context=_form_context(
                mode="create",
                action="/proposals",
                values=raw,
                errors={"project_name": str(exc)},
            ),
            status_code=409,
        )

    # 303, not 302: it explicitly tells the browser to follow up with a
    # GET, which is exactly the post/redirect/get behaviour intended, so
    # pressing refresh afterwards re-fetches the list rather than
    # re-submitting the form and creating a duplicate. Redirects to the
    # list, not the detail page, because seeing the new row among the
    # others is the confirmation that the submission worked.
    return RedirectResponse("/proposals", status_code=303)


@router.get("/proposals/{proposal_id}")
def proposal_detail(
    request: Request, proposal_id: UUID, db: Session = Depends(get_db)
) -> object:
    """Show one proposal, or a 404 page if it does not exist or was deleted."""
    try:
        proposal = get_proposal(proposal_id, ProposalRepository(db))
    except ProposalNotFoundError:
        # Translating the domain error into an HTTP status is the
        # route's job - the service layer does not do this itself,
        # because it does not know an HTTP status code exists.
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return templates.TemplateResponse(
        request=request, name="detail.html", context={"proposal": proposal}
    )


@router.get("/proposals/{proposal_id}/edit")
def edit_proposal_form(
    request: Request, proposal_id: UUID, db: Session = Depends(get_db)
) -> object:
    """Show the same form as creation, pre-filled with the stored values."""
    try:
        proposal = get_proposal(proposal_id, ProposalRepository(db))
    except ProposalNotFoundError:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return templates.TemplateResponse(
        request=request,
        name="form.html",
        context=_form_context(
            mode="edit",
            action=f"/proposals/{proposal_id}",
            values=_values_from(proposal),
            proposal=proposal,
        ),
    )


@router.post("/proposals/{proposal_id}")
def update_proposal_submit(
    request: Request,
    proposal_id: UUID,
    project_name: str = Form(""),
    country: str = Form(""),
    category: str = Form(""),
    budget_usd: str = Form(""),
    start_date: str = Form(""),
    summary: str = Form(""),
    db: Session = Depends(get_db),
) -> object:
    """Validate an edited proposal and save it, or re-render the form."""
    repo = ProposalRepository(db)
    action = f"/proposals/{proposal_id}"

    # Fetched up front, before validating the submitted data: an edit
    # form for an id that no longer exists should 404 regardless of
    # whether what was typed happens to be valid, and the object is
    # needed either way to render the Cancel link on a failed re-render.
    try:
        proposal = get_proposal(proposal_id, repo)
    except ProposalNotFoundError:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    raw = _raw_form(project_name, country, category, budget_usd, start_date, summary)

    try:
        data = ProposalUpdate(**raw)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request=request,
            name="form.html",
            context=_form_context(
                mode="edit",
                action=action,
                values=raw,
                errors=format_errors(exc),
                proposal=proposal,
            ),
            status_code=400,
        )

    try:
        update_proposal(proposal_id, data, repo)
    except DuplicateProposalError as exc:
        return templates.TemplateResponse(
            request=request,
            name="form.html",
            context=_form_context(
                mode="edit",
                action=action,
                values=raw,
                errors={"project_name": str(exc)},
                proposal=proposal,
            ),
            status_code=409,
        )

    # Redirects to the detail page, not the list: after changing
    # something a person expects to see the thing they just changed,
    # unlike creation, where the confirmation is seeing the new row
    # appear among the others.
    return RedirectResponse(action, status_code=303)


@router.post("/proposals/{proposal_id}/delete")
def delete_proposal_submit(
    proposal_id: UUID, db: Session = Depends(get_db)
) -> object:
    """Soft-delete a proposal and return to the list."""
    try:
        delete_proposal(proposal_id, ProposalRepository(db))
    except ProposalNotFoundError:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return RedirectResponse("/proposals", status_code=303)
