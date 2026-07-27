from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "CTAF climate technology project proposal intake. "
        "The browser interface is served from /proposals; "
        "the read-only JSON API is documented below."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# Static mount, both routers, and the HTML-aware exception handler are added
# in Phases 4-5 (Modules 11-14), once app/static/ and the routers exist.


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Send the bare domain to the list page."""
    return RedirectResponse(url="/proposals", status_code=307)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Liveness probe used by the container and by smoke tests."""
    return {"status": "ok"}
