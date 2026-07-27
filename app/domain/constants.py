from datetime import date
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

DATA_DIR = Path(__file__).resolve().parent / "data"
COUNTRIES_FILE = DATA_DIR / "gggi_members.txt"


class Category(str, Enum):
    """The five climate technology categories from the assignment."""

    RENEWABLE_ENERGY = "renewable_energy"
    MRV = "mrv"
    SMART_GRID = "smart_grid"
    CLIMATE_RISK_MAPPING = "climate_risk_mapping"
    OTHER = "other"


CATEGORY_LABELS: dict[Category, str] = {
    Category.RENEWABLE_ENERGY: "Renewable Energy",
    Category.MRV: "Carbon Measurement (MRV)",
    Category.SMART_GRID: "Smart Grid",
    Category.CLIMATE_RISK_MAPPING: "Climate Risk Mapping",
    Category.OTHER: "Other",
}

CATEGORY_CHOICES: list[tuple[str, str]] = [
    (category.value, CATEGORY_LABELS[category]) for category in Category
]


class CountryRecord(NamedTuple):
    """One GGGI member country."""

    code: str
    name: str
    joined: date | None


@lru_cache(maxsize=1)
def load_countries() -> tuple[CountryRecord, ...]:
    """Read the curated GGGI member list, sorted by display name.

    The single seam between the rest of the application and where the
    country list physically lives. Today it parses a text file; when
    the list moves into a `countries` table this body becomes a query
    and no caller changes.
    """
    if not COUNTRIES_FILE.exists():
        raise FileNotFoundError(f"Country data file not found: {COUNTRIES_FILE}")

    records: list[CountryRecord] = []
    for line_number, raw in enumerate(
        COUNTRIES_FILE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            raise ValueError(
                f"{COUNTRIES_FILE.name} line {line_number}: "
                f"expected 3 pipe-separated fields, got {len(parts)}"
            )
        code, name, joined_raw = parts
        if len(code) != 2 or not code.isalpha() or code != code.upper():
            raise ValueError(
                f"{COUNTRIES_FILE.name} line {line_number}: "
                f"{code!r} is not an uppercase ISO 3166-1 alpha-2 code"
            )
        joined = date.fromisoformat(joined_raw) if joined_raw else None
        records.append(CountryRecord(code=code, name=name, joined=joined))

    if not records:
        raise ValueError(f"{COUNTRIES_FILE.name} contains no country records")

    return tuple(sorted(records, key=lambda record: record.name))


@lru_cache(maxsize=1)
def country_choices() -> list[tuple[str, str]]:
    """Ordered (code, display name) pairs for rendering <select> options."""
    return [(record.code, record.name) for record in load_countries()]


@lru_cache(maxsize=1)
def country_codes() -> frozenset[str]:
    """Every valid country code, for validation."""
    return frozenset(record.code for record in load_countries())


def country_label(code: str) -> str:
    """Display name for a stored country code; the code itself if unknown."""
    for record in load_countries():
        if record.code == code:
            return record.name
    return code


def category_label(code: str) -> str:
    """Display name for a stored category code; the code itself if unknown."""
    try:
        return CATEGORY_LABELS[Category(code)]
    except ValueError:
        return code
