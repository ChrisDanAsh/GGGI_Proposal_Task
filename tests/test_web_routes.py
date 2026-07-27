# Web route tests (Module 13, exercising the templates from Module 11
# and the static assets from Module 12 as a side effect of rendering) -
# W-1 through W-28 from the architecture doc's test plan, §6.4. Full
# requests through TestClient, so route, schema, service, repository,
# and template all run together exactly as they would in production.

import re

from fastapi.testclient import TestClient

from app.db.repository import ProposalRepository
from app.schemas.proposal import ProposalCreate
from app.services.proposal import create_proposal

# Matches an inline event-handler attribute like onsubmit= or onclick=,
# case-insensitively. Used by W-27/W-28 to assert the codebase's
# absolute rule that no such attribute appears anywhere in rendered HTML
# (see app/templates/detail.html for why: HTML escaping is correct for
# an HTML attribute context but not a JavaScript one, so an inline
# handler is the one place autoescaping does not protect against XSS).
_INLINE_HANDLER = re.compile(r"\bon\w+\s*=", re.IGNORECASE)

# The literal `required` boolean attribute, matched only when it stands
# alone as a token (preceded and followed by whitespace or `>`) so it is
# not confused with the unrelated `class="required"` marker used for the
# asterisk next to a field's label.
_REQUIRED_ATTR = re.compile(r"(?<=\s)required(?=[\s>])")


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


def _seed(repo: ProposalRepository, **overrides: object):
    return create_proposal(ProposalCreate(**_payload(**overrides)), repo)


def _form_data(**overrides: object) -> dict[str, str]:
    """A POST body for the create/edit routes - all six fields as strings,
    matching what a browser's <form> actually submits."""
    data: dict[str, str] = {
        "project_name": "Solar Mini-Grid",
        "country": "KE",
        "category": "renewable_energy",
        "budget_usd": "50000",
        "start_date": "",
        "summary": "",
    }
    data.update(overrides)
    return data


# W-1 - the liveness probe
def test_w1_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# W-2 - the root redirect
def test_w2_root_redirects_to_proposals(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/proposals"


# W-3 - the empty form renders every field and the full vocabularies
def test_w3_new_form_has_all_fields_and_choices(client: TestClient) -> None:
    response = client.get("/proposals/new")
    assert response.status_code == 200
    body = response.text
    for field in (
        "project_name",
        "country",
        "category",
        "budget_usd",
        "start_date",
        "summary",
    ):
        assert f'name="{field}"' in body
    # 1 placeholder + 54 countries in the country <select>, plus 1
    # placeholder + 5 categories in the category <select> = 61 options.
    assert body.count("<option") == 61
    assert 'value="KE"' in body and "Kenya" in body
    for category_value in (
        "renewable_energy",
        "mrv",
        "smart_grid",
        "climate_risk_mapping",
        "other",
    ):
        assert f'value="{category_value}"' in body


# W-4 [REQ] - a valid submission creates the proposal and redirects
def test_w4_valid_submission_creates_and_redirects(client: TestClient) -> None:
    response = client.post(
        "/proposals", data=_form_data(), follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/proposals"


# W-5 - following the redirect shows the new proposal in the list
def test_w5_redirect_target_shows_new_proposal(client: TestClient) -> None:
    client.post(
        "/proposals",
        data=_form_data(project_name="Unique Redirect Target"),
        follow_redirects=False,
    )
    response = client.get("/proposals")
    assert response.status_code == 200
    assert "Unique Redirect Target" in response.text


# W-6 [REQ] - an empty project name is rejected, nothing is created
def test_w6_empty_project_name_rejected(
    client: TestClient, repo: ProposalRepository
) -> None:
    response = client.post("/proposals", data=_form_data(project_name=""))
    assert response.status_code == 400
    assert "Project name is required." in response.text
    assert repo.list() == []


# W-7 [REQ] - a negative budget is rejected
def test_w7_negative_budget_rejected(client: TestClient) -> None:
    response = client.post("/proposals", data=_form_data(budget_usd="-100"))
    assert response.status_code == 400
    assert "greater than zero" in response.text


# W-8 [REQ] - a summary over 300 characters is rejected
def test_w8_summary_too_long_rejected(client: TestClient) -> None:
    response = client.post("/proposals", data=_form_data(summary="x" * 301))
    assert response.status_code == 400
    assert "300 characters or fewer" in response.text


# W-9 - nothing typed is lost on a failed submission
def test_w9_failed_submission_preserves_values(client: TestClient) -> None:
    response = client.post(
        "/proposals",
        data=_form_data(
            project_name="Kept Name",
            country="KE",
            category="smart_grid",
            budget_usd="-100",
            start_date="2026-09-01",
            summary="Kept summary text.",
        ),
    )
    assert response.status_code == 400
    body = response.text
    assert 'value="Kept Name"' in body
    assert 'value="KE" selected' in body
    assert 'value="smart_grid" selected' in body
    assert 'value="2026-09-01"' in body
    assert "Kept summary text." in body


# W-10 - a duplicate name is rejected with 409
def test_w10_duplicate_name_rejected(
    client: TestClient, repo: ProposalRepository
) -> None:
    _seed(repo, project_name="Already Exists")
    response = client.post(
        "/proposals", data=_form_data(project_name="Already Exists")
    )
    assert response.status_code == 409
    assert "already exists" in response.text


# W-11 - an empty start date is stored as None
def test_w11_empty_start_date_stored_as_none(
    client: TestClient, repo: ProposalRepository
) -> None:
    client.post(
        "/proposals",
        data=_form_data(project_name="No Start Date", start_date=""),
        follow_redirects=False,
    )
    stored = next(p for p in repo.list() if p.project_name == "No Start Date")
    assert stored.start_date is None


# W-11b - an empty summary is accepted, the field is optional
def test_w11b_empty_summary_accepted(
    client: TestClient, repo: ProposalRepository
) -> None:
    response = client.post(
        "/proposals",
        data=_form_data(project_name="No Summary Here", summary=""),
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = next(p for p in repo.list() if p.project_name == "No Summary Here")
    assert stored.summary == ""


# W-11c - the detail page states plainly that there is no summary
def test_w11c_detail_page_shows_no_summary_message(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Summary-less Proposal", summary="")
    response = client.get(f"/proposals/{proposal.id}")
    assert "No summary provided." in response.text


# W-12 [REQ] - filtering by country
def test_w12_filter_by_country(
    client: TestClient, repo: ProposalRepository
) -> None:
    _seed(repo, project_name="Kenyan Solar Project", country="KE")
    _seed(repo, project_name="Ethiopian Grid Project", country="ET")
    response = client.get("/proposals?country=KE")
    assert response.status_code == 200
    assert "Kenyan Solar Project" in response.text
    assert "Ethiopian Grid Project" not in response.text


# W-13 - filtering by category
def test_w13_filter_by_category(
    client: TestClient, repo: ProposalRepository
) -> None:
    _seed(repo, project_name="Grid Sensor Project", category="smart_grid")
    _seed(repo, project_name="Solar Farm Project", category="renewable_energy")
    response = client.get("/proposals?category=smart_grid")
    assert "Grid Sensor Project" in response.text
    assert "Solar Farm Project" not in response.text


# W-14 - an unknown country filter degrades to the unfiltered list
def test_w14_unknown_country_filter_is_unfiltered(
    client: TestClient, repo: ProposalRepository
) -> None:
    _seed(repo, project_name="Visible Regardless")
    response = client.get("/proposals?country=ZZ")
    assert response.status_code == 200
    assert "Visible Regardless" in response.text


# W-15 - the empty-database message
def test_w15_empty_list_shows_message(client: TestClient) -> None:
    response = client.get("/proposals")
    assert response.status_code == 200
    assert "No proposals yet" in response.text


# W-16 - the detail page shows the summary and formatted budget
def test_w16_detail_page_shows_summary_and_budget(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(
        repo,
        project_name="Detail Page Subject",
        budget_usd="123456.78",
        summary="A distinctive summary sentence.",
    )
    response = client.get(f"/proposals/{proposal.id}")
    assert response.status_code == 200
    assert "A distinctive summary sentence." in response.text
    assert "$123,456.78" in response.text


# W-17 - an unknown id renders the styled error page, not JSON
def test_w17_unknown_id_returns_styled_404(client: TestClient) -> None:
    import uuid

    response = client.get(f"/proposals/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "Proposal not found." in response.text


# W-18 - a soft-deleted proposal 404s too
def test_w18_deleted_proposal_returns_404(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Will Be Deleted")
    client.post(f"/proposals/{proposal.id}/delete", follow_redirects=False)
    response = client.get(f"/proposals/{proposal.id}")
    assert response.status_code == 404


# W-19 - the edit form is pre-filled, dates in the input format
def test_w19_edit_form_prefilled(
    client: TestClient, repo: ProposalRepository
) -> None:
    from datetime import date

    proposal = _seed(
        repo,
        project_name="Prefilled Proposal",
        country="VN",
        category="mrv",
        budget_usd="42000.50",
        start_date=date(2026, 9, 1).isoformat(),
        summary="Existing summary.",
    )
    response = client.get(f"/proposals/{proposal.id}/edit")
    assert response.status_code == 200
    body = response.text
    assert 'value="Prefilled Proposal"' in body
    assert 'value="VN" selected' in body
    assert 'value="mrv" selected' in body
    assert 'value="42000.50"' in body
    assert 'value="2026-09-01"' in body
    assert "Existing summary." in body


# W-20 - a valid edit changes the stored name and redirects to the detail page
def test_w20_valid_edit_updates_and_redirects(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Original Name")
    response = client.post(
        f"/proposals/{proposal.id}",
        data=_form_data(project_name="Changed Name"),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/proposals/{proposal.id}"
    assert repo.get(proposal.id).project_name == "Changed Name"


# W-21 - an invalid edit re-renders in edit mode, posting back to the same URL
def test_w21_invalid_edit_rerenders_in_edit_mode(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Editable Proposal")
    response = client.post(
        f"/proposals/{proposal.id}",
        data=_form_data(budget_usd="-5"),
    )
    assert response.status_code == 400
    assert f'action="/proposals/{proposal.id}"' in response.text
    assert "Save changes" in response.text


# W-22 [REQ] - deleting removes it from the list and 404s its detail page
def test_w22_delete_removes_proposal(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="To Be Deleted")
    response = client.post(
        f"/proposals/{proposal.id}/delete", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/proposals"
    assert "To Be Deleted" not in client.get("/proposals").text
    assert client.get(f"/proposals/{proposal.id}").status_code == 404


# W-23 - deleting an unknown id 404s
def test_w23_delete_unknown_id_returns_404(client: TestClient) -> None:
    import uuid

    response = client.post(f"/proposals/{uuid.uuid4()}/delete")
    assert response.status_code == 404


# W-24 - the browser-side checks are actually rendered
def test_w24_browser_side_validation_attributes_present(
    client: TestClient,
) -> None:
    body = client.get("/proposals/new").text
    assert 'maxlength="300"' in body
    assert 'min="0.01"' in body
    assert _REQUIRED_ATTR.search(body) is not None
    assert "counter.js" in body


# W-24b - no stray novalidate attribute anywhere on the form
def test_w24b_no_novalidate_attribute(client: TestClient) -> None:
    body = client.get("/proposals/new").text
    assert "novalidate" not in body


# W-24c - required appears exactly on the four required fields
def test_w24c_exactly_four_required_attributes(client: TestClient) -> None:
    body = client.get("/proposals/new").text
    assert len(_REQUIRED_ATTR.findall(body)) == 4


# W-25 - a script tag in a summary is escaped in an HTML text context
def test_w25_summary_with_script_tag_is_escaped(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(
        repo,
        project_name="XSS Summary Test",
        summary="<script>alert(1)</script>",
    )
    response = client.get(f"/proposals/{proposal.id}")
    assert "&lt;script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text


# W-27 - the regression test for the inline-handler XSS described in
# app/templates/detail.html: a dangerous project name must never end up
# inside an inline event handler or a <script> body, only inside the
# data-project-name attribute.
def test_w27_dangerous_name_has_no_inline_handler(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="'); alert(1); //")
    response = client.get(f"/proposals/{proposal.id}")
    body = response.text
    assert _INLINE_HANDLER.search(body) is None
    assert "<script>" not in body
    assert "data-project-name=" in body


# W-28 - no inline event-handler attribute anywhere, across every page
def test_w28_no_inline_handlers_on_any_page(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Page Sweep Subject")
    pages = [
        "/proposals/new",
        "/proposals",
        f"/proposals/{proposal.id}",
        f"/proposals/{proposal.id}/edit",
    ]
    for path in pages:
        body = client.get(path).text
        assert _INLINE_HANDLER.search(body) is None, f"inline handler found on {path}"


# W-26 - parameterisation holds against a classic SQL injection payload
def test_w26_sql_injection_payload_stored_literally(
    client: TestClient, repo: ProposalRepository
) -> None:
    payload_name = "'; DROP TABLE proposals; --"
    response = client.post(
        "/proposals",
        data=_form_data(project_name=payload_name),
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = next(p for p in repo.list() if p.project_name == payload_name)
    assert stored.project_name == payload_name
    # The table must still exist and be queryable - if it were dropped,
    # this call itself would raise.
    assert isinstance(repo.list(), list)
