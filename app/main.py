# This module assembles the whole application object: FastAPI reads it to
# know what routes exist, and uvicorn imports `app` from here to serve it
# (`uvicorn app.main:app`). Nothing else in the codebase should define
# routes directly on an app object other than this one.

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.web import proposals as web_proposals
from app.web.templates import templates

# Derived from __file__, not written as the relative string "app/static" -
# a relative path resolves against the working directory, which differs
# between a laptop, a test runner, and a container, and would produce a
# startup crash that is tedious to trace back to its real cause.
STATIC_DIR = Path(__file__).resolve().parent / "static"

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

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(web_proposals.router)
# The JSON API router (Module 14, Phase 5) is included here once it
# exists; nothing above depends on it, so this file needs only one more
# line - `app.include_router(api_proposals.router)` - when that module lands.


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """Render a styled HTML error page for a browser request.

    Registered on Starlette's own HTTPException (not FastAPI's re-export)
    so it also catches errors raised inside Starlette itself, such as an
    unmatched route producing a plain 404 before any route code runs.
    Branches on the path prefix so a future /api/... request (Module 14)
    keeps getting a JSON error body it can parse, while every HTML route
    in this module gets a page that still looks like the rest of the site
    (error.html) rather than a bare JSON object.
    """
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail}
        )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


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
