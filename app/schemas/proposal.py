# Everything arriving from a browser is text: "50000" is a string, not a
# number; "banana" might land where a budget was expected; an untouched
# date input posts "" rather than nothing at all. This module is what
# checks and converts that text before any other layer touches it, and it
# is the check that cannot be skipped - the browser's `required` and
# `maxlength` attributes run on someone else's computer and can be deleted
# from developer tools in seconds.

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.domain.constants import Category, country_codes


def _known_country(code: str) -> str:
    """Reject a country code that is not a current GGGI member.

    A <select> in the form only ever offers a real GGGI member, but a
    country code also reaches this schema from the filter query string,
    the JSON API, and scripts/seed.py - none of which go through that
    dropdown - so the membership check has to run here, not just in HTML.
    """
    normalised = code.strip().upper()
    if normalised not in country_codes():
        raise ValueError("Unknown country code")
    return normalised


# Annotated + AfterValidator, not a Country enum: the country list is
# runtime data loaded from a file (Module 2) and will later come from a
# database table, so validation has to be a membership check against
# country_codes() rather than a fixed set of enum members baked in at
# import time.
CountryCode = Annotated[str, AfterValidator(_known_country)]


class ProposalBase(BaseModel):
    """Fields and rules shared by creation and editing."""

    # Strips leading/trailing whitespace from every string field before
    # any other rule runs. On project_name this is what makes
    # min_length=1 mean "has actual content" rather than "has any
    # characters at all" (so "   " is rejected). On summary it collapses
    # a textarea containing only spaces down to "".
    model_config = ConfigDict(str_strip_whitespace=True)

    project_name: str = Field(min_length=1, max_length=200)
    country: CountryCode
    category: Category
    # gt=0 rejects zero as well as negative numbers - "greater than",
    # not "greater than or equal to". max_digits/decimal_places mirror
    # the database's NUMERIC(15, 2) column exactly.
    budget_usd: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    start_date: date | None = None
    # Defaults to "" rather than None: the database column is NOT NULL,
    # and allowing both NULL and "" to mean "no summary" would be two
    # representations of the same thing. The assignment never marks a
    # minimum length, so the field is optional.
    summary: str = Field(default="", max_length=300)

    @field_validator("start_date", mode="before")
    @classmethod
    def _empty_string_is_no_date(cls, value: Any) -> Any:
        """An untouched date input posts "", which means 'not provided'.

        Without this coercion every proposal submitted without a start
        date would fail with an unintelligible date-parsing error, even
        though the field is explicitly optional.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("budget_usd", mode="before")
    @classmethod
    def _normalise_budget(cls, value: Any) -> Any:
        """Strip thousands separators and surrounding spaces before parsing.

        A person typing 250,000 is entering a plausible budget; rejecting
        it as unparseable would be needlessly hostile for two lines of code.
        """
        if isinstance(value, str):
            return value.strip().replace(",", "")
        return value


class ProposalCreate(ProposalBase):
    """Validated payload for creating a proposal."""


class ProposalUpdate(ProposalBase):
    """Validated payload for editing a proposal. Same rules as creation.

    Kept as its own class, even though it adds nothing today, so there is
    a natural home for any rule that eventually differs between creating
    and editing, and so route signatures stay self-documenting.
    """


class ProposalRead(BaseModel):
    """What the JSON API returns.

    Deliberately restates its fields rather than inheriting from
    ProposalBase: this is an output shape, not an input one. country and
    category are returned as plain strings (the stored code), because a
    JSON consumer should not have to know about a Python enum.
    deleted_at and owner_id are omitted - deleted rows are never
    returned, so the former would always be null, and owner_id is unused.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_name: str
    country: str
    category: str
    budget_usd: Decimal
    start_date: date | None
    summary: str
    created_at: datetime
    updated_at: datetime


# Keyed by (field name, Pydantic error type), not by field name alone:
# "", "abc", "0", and "-5" in the budget box are four different mistakes
# and deserve four different messages, which a field-only key could never
# produce.
_ERROR_MESSAGES: dict[tuple[str, str], str] = {
    ("project_name", "missing"): "Project name is required.",
    ("project_name", "string_too_short"): "Project name is required.",
    ("project_name", "string_too_long"): "Project name must be 200 characters or fewer.",
    ("country", "missing"): "Select a target country.",
    ("country", "value_error"): "Select a target country from the list.",
    ("country", "string_type"): "Select a target country from the list.",
    ("category", "missing"): "Select a climate technology category.",
    ("category", "enum"): "Select a climate technology category from the list.",
    ("budget_usd", "missing"): "Estimated budget is required.",
    ("budget_usd", "decimal_parsing"): "Estimated budget must be a number.",
    ("budget_usd", "greater_than"): "Estimated budget must be greater than zero.",
    ("budget_usd", "decimal_max_places"): "Estimated budget may have at most 2 decimal places.",
    ("budget_usd", "decimal_whole_digits"): "Estimated budget is too large.",
    ("budget_usd", "decimal_max_digits"): "Estimated budget is too large.",
    ("start_date", "date_parsing"): "Planned start date must be a valid date.",
    ("start_date", "date_from_datetime_parsing"): "Planned start date must be a valid date.",
    ("start_date", "date_type"): "Planned start date must be a valid date.",
    ("summary", "string_too_long"): "Project summary must be 300 characters or fewer.",
}

# Reached only when a (field, error_type) pair above is not matched - a
# per-field message is still better than Pydantic's own wording, which
# reads as a machine talking to a machine ("Input should be greater than 0").
_FALLBACK_MESSAGES: dict[str, str] = {
    "project_name": "Please check the project name.",
    "country": "Please choose a target country.",
    "category": "Please choose a climate technology category.",
    "budget_usd": "Please enter a valid budget in USD.",
    "start_date": "Please enter a valid start date.",
    "summary": "Please check the project summary.",
}


def format_errors(exc: ValidationError) -> dict[str, str]:
    """Turn a ValidationError into {field name: one plain-English message}.

    Only the first error per field is kept - the form renders exactly one
    message beneath each input, so a list of errors for the same field
    would complicate the template for no gain.
    """
    messages: dict[str, str] = {}
    for error in exc.errors():
        location = error.get("loc") or ()
        field = str(location[0]) if location else "_form"
        if field in messages:
            continue
        key = (field, str(error.get("type", "")))
        messages[field] = _ERROR_MESSAGES.get(
            key,
            _FALLBACK_MESSAGES.get(field, "This value is not valid."),
        )
    return messages
