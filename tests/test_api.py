# API tests (Module 14) - A-1 through A-10 from the architecture doc's
# test plan, §6.5. These exercise the read-only JSON door, which reaches
# the identical service and repository calls the HTML routes use and
# diverges only on the final rendering step.

import re

from fastapi.testclient import TestClient

from app.db.repository import ProposalRepository
from app.schemas.proposal import ProposalCreate
from app.services.proposal import create_proposal, delete_proposal

_PROPOSAL_READ_FIELDS = {
    "id",
    "project_name",
    "country",
    "category",
    "budget_usd",
    "start_date",
    "summary",
    "created_at",
    "updated_at",
}


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


# A-1 - a basic list response has exactly the documented shape
def test_a1_list_proposals_shape(
    client: TestClient, repo: ProposalRepository
) -> None:
    _seed(repo, project_name="API Test One", country="KE")
    _seed(repo, project_name="API Test Two", country="ET")
    _seed(repo, project_name="API Test Three", country="VN")

    response = client.get("/api/proposals")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    for item in body:
        assert set(item.keys()) == _PROPOSAL_READ_FIELDS


# A-2 - filtering matches what the HTML list produces for the same filter
def test_a2_filter_matches_html_route(
    client: TestClient, repo: ProposalRepository
) -> None:
    _seed(repo, project_name="API Kenya Project", country="KE")
    _seed(repo, project_name="API Ethiopia Project", country="ET")

    api_names = {
        p["project_name"] for p in client.get("/api/proposals?country=KE").json()
    }
    assert api_names == {"API Kenya Project"}

    html_body = client.get("/proposals?country=KE").text
    assert "API Kenya Project" in html_body
    assert "API Ethiopia Project" not in html_body


# A-3 - an unknown country code is a 422, not silently ignored
def test_a3_unknown_country_code_rejected(client: TestClient) -> None:
    response = client.get("/api/proposals?country=ZZ")
    assert response.status_code == 422


# A-4 - a soft-deleted proposal is absent from the API too
def test_a4_soft_deleted_proposal_absent(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Will Be Deleted Via API Test")
    delete_proposal(proposal.id, repo)
    names = {p["project_name"] for p in client.get("/api/proposals").json()}
    assert "Will Be Deleted Via API Test" not in names


# A-5 - fetching a single proposal matches the stored row
def test_a5_get_single_proposal_matches_stored(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(
        repo, project_name="Single Fetch Target", budget_usd="12345.67"
    )
    response = client.get(f"/api/proposals/{proposal.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(proposal.id)
    assert body["project_name"] == "Single Fetch Target"
    assert body["budget_usd"] == "12345.67"


# A-6 - an unknown id is a JSON 404, not an HTML page
def test_a6_unknown_id_returns_json_404(client: TestClient) -> None:
    import uuid

    response = client.get(f"/api/proposals/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Proposal not found."}


# A-7 - no response ever exposes deleted_at or owner_id
def test_a7_no_internal_fields_exposed(
    client: TestClient, repo: ProposalRepository
) -> None:
    proposal = _seed(repo, project_name="Internal Fields Check")
    list_body = client.get("/api/proposals").json()
    detail_body = client.get(f"/api/proposals/{proposal.id}").json()
    for item in list_body + [detail_body]:
        assert "deleted_at" not in item
        assert "owner_id" not in item


# A-8 - the OpenAPI schema documents exactly the three JSON paths
def test_a8_openapi_documents_only_api_paths(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths) == {
        "/api/proposals",
        "/api/proposals/{proposal_id}",
        "/api/countries",
    }
    assert not any(path.startswith("/proposals") for path in paths)


# A-9 - the countries endpoint returns all 54, sorted by name
def test_a9_countries_endpoint_complete_and_sorted(client: TestClient) -> None:
    response = client.get("/api/countries")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 54
    for item in body:
        assert set(item.keys()) == {"code", "name", "joined"}
    names = [item["name"] for item in body]
    assert names == sorted(names)


# A-10 - the API's country codes are exactly the form dropdown's codes
def test_a10_countries_match_form_dropdown(client: TestClient) -> None:
    api_codes = {item["code"] for item in client.get("/api/countries").json()}

    form_body = client.get("/proposals/new").text
    dropdown_codes = set(re.findall(r'<option value="([A-Z]{2})"', form_body))

    assert api_codes == dropdown_codes
