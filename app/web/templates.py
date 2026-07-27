# The one place the Jinja environment is configured: the template
# directory, the country/category vocabularies handed to every template
# as globals, and the formatting filters for money and dates. Configuring
# it here means those things are defined once rather than repeated in
# every route that renders a page.

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.domain.constants import (
    CATEGORY_CHOICES,
    category_label,
    country_choices,
    country_label,
)

# Derived from __file__, not written as the relative string "app/templates" -
# a relative path resolves against the working directory, which differs
# between a laptop, a test runner, and a container (same reasoning as
# STATIC_DIR in app/main.py).
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Jinja2Templates enables autoescaping for .html files by default, which
# is the application's whole XSS defence: every value interpolated into
# a page is HTML-escaped, so a project summary containing <script> is
# displayed as text rather than executed. `|safe` must never appear in
# any template in this project - doing so would open exactly the hole
# autoescaping exists to close.
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _money(value: Decimal | None) -> str:
    """Render a budget as USD with thousands separators."""
    if value is None:
        return "—"
    return f"${value:,.2f}"


def _date_display(value: date | None) -> str:
    """Render a date as 05 Mar 2026, or an em dash when absent."""
    if value is None:
        return "—"
    return value.strftime("%d %b %Y")


def _date_input(value: date | None) -> str:
    """Render a date as YYYY-MM-DD, the only format <input type="date"> accepts."""
    if value is None:
        return ""
    return value.isoformat()


# Populated from the curated vocabularies (Module 2), not from
# `SELECT DISTINCT` over the proposals table - a filter list built from
# stored data would hide a country until a proposal existed for it and
# would change shape as rows come and go. country_choices() is called
# once here at import time because it is @lru_cache'd and the underlying
# file does not change while the process runs.
templates.env.globals["country_choices"] = country_choices()
templates.env.globals["category_choices"] = CATEGORY_CHOICES
templates.env.globals["app_name"] = "CTAF Proposal Portal"
templates.env.filters["country_label"] = country_label
templates.env.filters["category_label"] = category_label
templates.env.filters["money"] = _money
# Two separate date filters, not one: a person reads "05 Mar 2026", but
# an <input type="date"> requires "2026-03-05" and silently renders
# blank given anything else. Conflating them would leave the edit form's
# date box mysteriously empty.
templates.env.filters["date_display"] = _date_display
templates.env.filters["date_input"] = _date_input
