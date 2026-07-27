# Country data tests (Module 2) - C-1 through C-11 from the architecture
# doc's test plan, §6.1. The country list is data, not code, so it gets
# the tests data deserves: that it parses, that it is complete, and that
# malformed input fails loudly rather than producing a silently
# incomplete dropdown. No database, no web server.

from pathlib import Path
from unittest.mock import patch

import pytest

from app.domain import constants


def _clear_caches() -> None:
    """Every loader here is @lru_cache'd, so a test that monkeypatches
    COUNTRIES_FILE must clear these before AND after, or it either reads
    stale data or poisons the cache for every test that runs afterwards."""
    constants.load_countries.cache_clear()
    constants.country_choices.cache_clear()
    constants.country_codes.cache_clear()


@pytest.fixture()
def isolated_countries_file(tmp_path, monkeypatch):
    """Point COUNTRIES_FILE at a throwaway file for one test, then
    restore the real one and re-clear the caches so later tests are
    unaffected."""

    def _use(content: str) -> Path:
        countries_file = tmp_path / "gggi_members.txt"
        countries_file.write_text(content, encoding="utf-8")
        monkeypatch.setattr(constants, "COUNTRIES_FILE", countries_file)
        _clear_caches()
        return countries_file

    yield _use
    _clear_caches()


# C-1 - the shipped file parses into 54 well-formed records
def test_c1_load_countries_returns_54_valid_records() -> None:
    records = constants.load_countries()
    assert len(records) == 54
    codes = [r.code for r in records]
    assert all(len(code) == 2 and code.isalpha() and code.isupper() for code in codes)
    assert len(set(codes)) == len(codes)


# C-2 - spot-check known members and a known non-member
def test_c2_membership_spot_check() -> None:
    codes = constants.country_codes()
    for founding_member in ("DK", "GY"):
        assert founding_member in codes
    for recent_member in ("SB", "LU"):
        assert recent_member in codes
    # India is not a GGGI member - a plausible-looking code is still absent.
    assert "IN" not in codes


# C-3 - country_choices() is sorted by name; the file stays in accession order
def test_c3_choices_sorted_by_name_file_stays_in_accession_order() -> None:
    choices = constants.country_choices()
    names = [name for _code, name in choices]
    assert names == sorted(names)

    raw_lines = [
        line
        for line in constants.COUNTRIES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    # DK (2012-10-18) is the first accession in the source document;
    # LU (2026-03-12) is the most recent - the raw file order should
    # still reflect that even though the dropdown above is name-sorted.
    assert raw_lines[0].startswith("DK|")
    assert raw_lines[-1].startswith("LU|")


# C-4 - country_codes() is a frozenset matching load_countries()
def test_c4_country_codes_matches_load_countries() -> None:
    codes = constants.country_codes()
    assert isinstance(codes, frozenset)
    assert codes == {r.code for r in constants.load_countries()}
    assert len(codes) == 54


# C-5 - country_label() falls back to the code itself for an unknown value
def test_c5_country_label_known_and_unknown() -> None:
    assert constants.country_label("KE") == "Kenya"
    assert constants.country_label("ZZ") == "ZZ"


# C-6 - non-ASCII names survive the UTF-8 read intact
def test_c6_non_ascii_country_name() -> None:
    assert constants.country_label("CI") == "Côte d'Ivoire"


# C-7 - the loader caches: two calls return the identical object, and the
# file is read exactly once
def test_c7_load_countries_is_cached() -> None:
    constants.load_countries.cache_clear()
    with patch.object(
        Path, "read_text", wraps=Path.read_text, autospec=True
    ) as read_text:
        first = constants.load_countries()
        second = constants.load_countries()
    assert first is second
    assert read_text.call_count == 1


# C-8 - a line with the wrong number of fields names the file and line number
def test_c8_malformed_line_wrong_field_count(isolated_countries_file) -> None:
    isolated_countries_file("KE|Kenya\nET|Ethiopia|2013-08-04\n")
    with pytest.raises(ValueError) as exc_info:
        constants.load_countries()
    message = str(exc_info.value)
    assert "gggi_members.txt" in message
    assert "line 1" in message


# C-9 - a three-letter code names the offending code
def test_c9_malformed_line_bad_code(isolated_countries_file) -> None:
    isolated_countries_file("KEN|Kenya|2025-04-18\n")
    with pytest.raises(ValueError) as exc_info:
        constants.load_countries()
    assert "KEN" in str(exc_info.value)


# C-10 - a file of only comments and blank lines reports no records
def test_c10_no_records_reports_clearly(isolated_countries_file) -> None:
    isolated_countries_file("# just a header\n\n# nothing else\n")
    with pytest.raises(ValueError) as exc_info:
        constants.load_countries()
    assert "no country records" in str(exc_info.value)


# C-11 - a missing file names the expected path
def test_c11_missing_file(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "does_not_exist.txt"
    monkeypatch.setattr(constants, "COUNTRIES_FILE", missing)
    _clear_caches()
    try:
        with pytest.raises(FileNotFoundError) as exc_info:
            constants.load_countries()
        assert str(missing) in str(exc_info.value)
    finally:
        _clear_caches()
