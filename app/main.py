# This module assembles the whole application object: FastAPI reads it to
# know what routes exist, and uvicorn imports `app` from here to serve it
# (`uvicorn app.main:app`). Nothing else in the codebase should define
# routes directly on an app object other than this one.

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.config import get_settings

# Read once, at import time, rather than in every route - get_settings()
# is cached (Module 1), so this is the one parse of the environment.
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "CTAF climate technology project proposal intake. "
        "The browser interface is served from /proposals; "
        "the read-only JSON API is documented below."
    ),
    version="1.0.0",
    # FastAPI auto-generates an interactive API browser at /docs from the
    # route type annotations. Its ReDoc equivalent is disabled below since
    # one documentation UI is enough for this project.
    docs_url="/docs",
    redoc_url=None,
)

# Static mount, both routers, and the HTML-aware exception handler are added
# in Phases 4-5 (Modules 11-14), once app/static/ and the routers exist.
# Mounting StaticFiles against a directory that does not exist yet would
# crash the app at import time, and there is nothing for the routers to
# include until app/web/proposals.py and app/api/proposals.py are written.


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Send the bare domain to the list page.

    Uses a 307 redirect rather than 302: both behave the same for a GET
    request, but 307 explicitly preserves the HTTP method, so this
    redirect's behaviour cannot silently change if `/` ever needs to
    accept something other than GET.
    """
    return RedirectResponse(url="/proposals", status_code=307)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Liveness probe used by the container and by smoke tests.

    Deliberately does nothing but return a fixed value - it proves the
    web server itself is up, independent of whether the database is
    reachable, so it is safe to use as a container healthcheck.
    """
    return {"status": "ok"}
