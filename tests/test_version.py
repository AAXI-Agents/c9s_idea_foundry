"""Tests for the version module."""

from datetime import date

from crewai_productfeature_planner.version import (
    _CODEX,
    CodexEntry,
    __version__,
    get_codex,
    get_latest_codex_entry,
    get_version,
)


class TestGetVersion:
    def test_returns_string(self):
        assert isinstance(get_version(), str)

    def test_matches_module_level(self):
        assert get_version() == __version__

    def test_semver_format(self):
        parts = get_version().split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_current_version(self):
        assert get_version() == "0.8.2"


class TestCodex:
    def test_codex_not_empty(self):
        codex = get_codex()
        assert len(codex) >= 1

    def test_codex_entries_have_required_keys(self):
        for entry in get_codex():
            assert "version" in entry
            assert "date" in entry
            assert "summary" in entry

    def test_codex_dates_are_iso_strings(self):
        for entry in get_codex():
            # Should parse without error
            date.fromisoformat(entry["date"])

    def test_latest_entry_matches_version(self):
        latest = get_latest_codex_entry()
        assert latest["version"] == get_version()

    def test_latest_is_last_codex_entry(self):
        codex = get_codex()
        latest = get_latest_codex_entry()
        assert codex[-1] == latest

    def test_codex_entry_is_named_tuple(self):
        entry = _CODEX[0]
        assert isinstance(entry, CodexEntry)
        assert hasattr(entry, "version")
        assert hasattr(entry, "date")
        assert hasattr(entry, "summary")

    def test_versions_are_unique(self):
        versions = [e.version for e in _CODEX]
        assert len(versions) == len(set(versions)), "Duplicate versions in codex"
