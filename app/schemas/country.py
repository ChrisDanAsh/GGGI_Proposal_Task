# A separate file from proposal.py because this describes a different
# thing - a country, not a proposal - and because when the country list
# eventually moves into a SQL table (see the architecture doc's future
# works section), this is the shape that table's rows will be serialised
# as. Used only by GET /api/countries.

from datetime import date

from pydantic import BaseModel


class CountryOut(BaseModel):
    """A GGGI member country as returned by the API."""

    code: str
    name: str
    joined: date | None
