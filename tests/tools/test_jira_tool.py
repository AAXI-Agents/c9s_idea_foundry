"""Tests for the Atlassian Jira ticket creation tool."""

import base64
from unittest.mock import MagicMock, patch

import pytest

import json

import crewai_productfeature_planner.tools.jira_tool as _jira_mod
import crewai_productfeature_planner.tools.jira._helpers as _jira_helpers_mod
from crewai_productfeature_planner.tools.jira_tool import (
    JiraCreateIssueTool,
    _build_auth_header,
    _drop_rejected_fields,
    _fetch_priority_scheme,
    _get_jira_env,
    _has_jira_credentials,
    _inline_marks,
    _markdown_to_adf,
    _markdown_to_wiki,
    _normalize_priority,
    _project_key_ctx,
    _resolve_priority_field,
    _run_id_label,
    _strip_emails,
    create_issue_link,
    create_jira_issue,
    jira_project_context,
    search_jira_issues,
    set_jira_project_key,
)


def _adf_to_text(adf: dict) -> str:
    """Recursively extract all text from an ADF document for assertions."""
    if not isinstance(adf, dict):
        return ""
    parts: list[str] = []
    if adf.get("type") == "text":
        parts.append(adf.get("text", ""))
    if adf.get("type") == "hardBreak":
        parts.append("\n")
    for child in adf.get("content", []):
        parts.append(_adf_to_text(child))
    return "".join(parts)


@pytest.fixture(autouse=True)
def _reset_priority_cache():
    """Reset the module-level priority scheme cache between tests."""
    _jira_helpers_mod._priority_id_cache = None
    yield
    _jira_helpers_mod._priority_id_cache = None


# ── _get_jira_env ────────────────────────────────────────────────────


class TestGetJiraEnv:

    def test_all_vars_set(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_jira_env()
        assert env["base_url"] == "https://example.atlassian.net"
        assert env["project_key"] == "PRD"
        assert env["username"] == "user@example.com"
        assert env["api_token"] == "secret"

    def test_missing_base_url(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        with pytest.raises(EnvironmentError, match="ATLASSIAN_BASE_URL"):
            _get_jira_env()

    def test_missing_all_vars(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)

        with pytest.raises(EnvironmentError):
            _get_jira_env()

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_jira_env()
        assert env["base_url"] == "https://example.atlassian.net"


# ── _jira_request (HTTP layer) ────────────────────────────────────────


class TestJiraRequest:
    """Tests for the low-level _jira_request function."""

    @patch("crewai_productfeature_planner.tools.jira._http.urllib.request.urlopen")
    def test_empty_response_body_returns_empty_dict(self, mock_urlopen):
        """201 Created with an empty body (e.g. issue-link) must not crash."""
        from crewai_productfeature_planner.tools.jira._http import _jira_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _jira_request(
            "POST",
            "https://example.atlassian.net/rest/api/3/issueLink",
            auth_header="Basic dGVzdA==",
            data={"type": {"name": "Blocks"}, "inwardIssue": {"key": "A-1"}, "outwardIssue": {"key": "A-2"}},
        )
        assert result == {}

    @patch("crewai_productfeature_planner.tools.jira._http.urllib.request.urlopen")
    def test_whitespace_only_body_returns_empty_dict(self, mock_urlopen):
        """Body with only whitespace/newlines should also return {}."""
        from crewai_productfeature_planner.tools.jira._http import _jira_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"  \n  "
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _jira_request(
            "GET",
            "https://example.atlassian.net/rest/api/3/issue/X-1",
            auth_header="Basic dGVzdA==",
        )
        assert result == {}

    @patch("crewai_productfeature_planner.tools.jira._http.urllib.request.urlopen")
    def test_json_body_parsed_normally(self, mock_urlopen):
        """Normal JSON body parsing still works."""
        from crewai_productfeature_planner.tools.jira._http import _jira_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"key": "X-1"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _jira_request(
            "POST",
            "https://example.atlassian.net/rest/api/3/issue",
            auth_header="Basic dGVzdA==",
            data={"fields": {}},
        )
        assert result == {"key": "X-1"}


# ── _has_jira_credentials ────────────────────────────────────────────


class TestHasJiraCredentials:

    def test_all_set(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        assert _has_jira_credentials() is True

    def test_missing(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        assert _has_jira_credentials() is False


# ── _build_auth_header ───────────────────────────────────────────────


def test_build_auth_header():
    header = _build_auth_header("admin@company.io", "tok123")
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header.split(" ")[1]).decode()
    assert decoded == "admin@company.io:tok123"


# ── create_jira_issue ────────────────────────────────────────────────


class TestCreateJiraIssue:

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_creates_story(self, mock_request):
        # First call is search (GET) → no existing issues; second is create (POST)
        mock_request.side_effect = [
            {"issues": []},
            {"key": "PRD-101", "id": "10101"},
        ]

        result = create_jira_issue(
            summary="Add dark mode",
            description="Implement dark mode toggle",
            run_id="run-1",
        )

        assert result["issue_key"] == "PRD-101"
        assert result["issue_id"] == "10101"
        assert "PRD-101" in result["url"]
        assert mock_request.call_count == 2  # search + create
        # The create call is the second one
        payload = mock_request.call_args_list[1][1]["data"]
        assert payload["fields"]["issuetype"]["name"] == "Story"
        assert payload["fields"]["summary"] == "Add dark mode"
        # description is now ADF (Atlassian Document Format)
        desc = payload["fields"]["description"]
        assert desc["type"] == "doc"
        assert desc["version"] == 1
        assert _adf_to_text(desc) == "Implement dark mode toggle"
        # run_id label should be auto-attached
        assert "prd-run-run-1" in payload["fields"]["labels"]

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_creates_epic(self, mock_request):
        mock_request.return_value = {"key": "PRD-200", "id": "20200"}

        result = create_jira_issue(
            summary="PRD — Dark Mode Feature",
            issue_type="Epic",
        )

        assert result["issue_key"] == "PRD-200"
        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["issuetype"]["name"] == "Epic"

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_epic_ignores_parent_key(self, mock_request):
        """Epics are top-level — epic_key must not produce a parent field."""
        mock_request.return_value = {"key": "PRD-201", "id": "20201"}

        create_jira_issue(
            summary="Top-level Epic",
            issue_type="Epic",
            epic_key="PRD-999",
        )

        payload = mock_request.call_args[1]["data"]
        assert "parent" not in payload["fields"]

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_epic_key_sets_parent(self, mock_request):
        mock_request.return_value = {"key": "PRD-301", "id": "30301"}

        create_jira_issue(
            summary="Story under epic",
            epic_key="PRD-200",
        )

        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["parent"] == {"key": "PRD-200"}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_labels_and_priority_with_scheme(self, mock_request):
        """When priority scheme is fetched successfully, use id."""
        mock_request.side_effect = [
            # 1st call: _fetch_priority_scheme GET
            [{"id": "1", "name": "Highest"}, {"id": "2", "name": "High"},
             {"id": "3", "name": "Medium"}, {"id": "4", "name": "Low"}],
            # 2nd call: POST create issue
            {"key": "PRD-401", "id": "40401"},
        ]

        create_jira_issue(
            summary="With labels",
            labels=["prd", "auto-generated"],
            priority="High",
        )

        # POST call is the second one
        payload = mock_request.call_args_list[1][1]["data"]
        assert payload["fields"]["labels"] == ["prd", "auto-generated"]
        assert payload["fields"]["priority"] == {"id": "2"}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_labels_and_priority_scheme_failure_fallback(self, mock_request):
        """When priority scheme fetch fails, fall back to name."""
        mock_request.side_effect = [
            # 1st call: _fetch_priority_scheme GET — fails
            RuntimeError("network error"),
            # 2nd call: POST create issue succeeds
            {"key": "PRD-401", "id": "40401"},
        ]

        create_jira_issue(
            summary="With labels",
            labels=["prd", "auto-generated"],
            priority="High",
        )

        # POST call is the second one
        payload = mock_request.call_args_list[1][1]["data"]
        assert payload["fields"]["labels"] == ["prd", "auto-generated"]
        assert payload["fields"]["priority"] == {"name": "High"}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_no_description_omitted(self, mock_request):
        mock_request.return_value = {"key": "PRD-501", "id": "50501"}

        create_jira_issue(summary="No desc")

        payload = mock_request.call_args[1]["data"]
        assert "description" not in payload["fields"]

    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_API_TOKEN")
        with pytest.raises(EnvironmentError, match="ATLASSIAN_API_TOKEN"):
            create_jira_issue(summary="Fail")

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_confluence_url_appended_to_description(self, mock_request):
        mock_request.return_value = {"key": "PRD-701", "id": "70701"}

        create_jira_issue(
            summary="Story with Confluence",
            description="Some requirement details",
            confluence_url="https://wiki.example.com/page/123",
        )

        payload = mock_request.call_args[1]["data"]
        desc = payload["fields"]["description"]
        assert desc["type"] == "doc"
        desc_text = _adf_to_text(desc)
        assert "https://wiki.example.com/page/123" in desc_text
        assert "Some requirement details" in desc_text
        assert "PRD Confluence page:" in desc_text

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_confluence_url_without_description(self, mock_request):
        mock_request.return_value = {"key": "PRD-702", "id": "70702"}

        create_jira_issue(
            summary="Epic with link only",
            issue_type="Epic",
            confluence_url="https://wiki.example.com/page/456",
        )

        payload = mock_request.call_args[1]["data"]
        desc = payload["fields"]["description"]
        assert desc["type"] == "doc"
        desc_text = _adf_to_text(desc)
        assert "https://wiki.example.com/page/456" in desc_text
        assert "PRD Confluence page:" in desc_text

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_no_confluence_url_omits_link(self, mock_request):
        mock_request.return_value = {"key": "PRD-703", "id": "70703"}

        create_jira_issue(
            summary="No link",
            description="Plain description",
        )

        payload = mock_request.call_args[1]["data"]
        desc_text = _adf_to_text(payload["fields"]["description"])
        assert "PRD Confluence page:" not in desc_text

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_component_sets_components_field(self, mock_request):
        mock_request.return_value = {"key": "PRD-801", "id": "80801"}

        create_jira_issue(
            summary="UX Story",
            component="UX",
        )

        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["components"] == [{"name": "UX"}]

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_no_component_omits_field(self, mock_request):
        mock_request.return_value = {"key": "PRD-802", "id": "80802"}

        create_jira_issue(summary="No component")

        payload = mock_request.call_args[1]["data"]
        assert "components" not in payload["fields"]


# ── _fetch_priority_scheme ────────────────────────────────────────────


class TestFetchPriorityScheme:
    """Tests for the priority scheme caching."""

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_fetches_and_caches(self, mock_request):
        mock_request.return_value = [
            {"id": "1", "name": "Highest"},
            {"id": "2", "name": "High"},
            {"id": "3", "name": "Medium"},
            {"id": "4", "name": "Low"},
            {"id": "5", "name": "Lowest"},
        ]

        result = _fetch_priority_scheme("Basic xxx", "https://x.atlassian.net")
        assert result == {
            "highest": "1", "high": "2", "medium": "3",
            "low": "4", "lowest": "5",
        }
        # Second call uses cache — no extra HTTP request
        result2 = _fetch_priority_scheme("Basic xxx", "https://x.atlassian.net")
        assert result2 is result
        assert mock_request.call_count == 1

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_returns_empty_on_failure(self, mock_request):
        mock_request.side_effect = RuntimeError("network error")

        result = _fetch_priority_scheme("Basic xxx", "https://x.atlassian.net")
        assert result == {}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_handles_nonstandard_priority_names(self, mock_request):
        """Projects with custom priority names like 'P0', 'P1'."""
        mock_request.return_value = [
            {"id": "10", "name": "P0 - Critical"},
            {"id": "11", "name": "P1 - High"},
            {"id": "12", "name": "P2 - Medium"},
        ]

        result = _fetch_priority_scheme("Basic xxx", "https://x.atlassian.net")
        assert result == {
            "p0 - critical": "10",
            "p1 - high": "11",
            "p2 - medium": "12",
        }


# ── _resolve_priority_field ──────────────────────────────────────────


class TestResolvePriorityField:
    """Tests for priority resolution using the cached scheme."""

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_resolves_to_id(self, mock_request):
        mock_request.return_value = [
            {"id": "2", "name": "High"},
            {"id": "3", "name": "Medium"},
        ]
        result = _resolve_priority_field("High", "Basic xxx", "https://x.atlassian.net")
        assert result == {"id": "2"}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_returns_none_when_not_in_scheme(self, mock_request):
        """When priority name doesn't exist in scheme, return None."""
        mock_request.return_value = [
            {"id": "10", "name": "P0 - Critical"},
        ]
        result = _resolve_priority_field("High", "Basic xxx", "https://x.atlassian.net")
        assert result is None

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_falls_back_to_name_on_fetch_failure(self, mock_request):
        """When scheme fetch fails, fall back to name format."""
        mock_request.side_effect = RuntimeError("timeout")
        result = _resolve_priority_field("High", "Basic xxx", "https://x.atlassian.net")
        assert result == {"name": "High"}


# ── create_issue_link ────────────────────────────────────────────────


class TestCreateIssueLink:

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_creates_blocks_link(self, mock_request):
        mock_request.return_value = {}

        create_issue_link("PRD-102", "PRD-101", link_type="Blocks")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/rest/api/3/issueLink" in call_args[0][1]
        payload = call_args[1]["data"]
        assert payload["type"]["name"] == "Blocks"
        assert payload["inwardIssue"]["key"] == "PRD-102"
        assert payload["outwardIssue"]["key"] == "PRD-101"

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_default_link_type_is_blocks(self, mock_request):
        mock_request.return_value = {}

        create_issue_link("PRD-200", "PRD-199")

        payload = mock_request.call_args[1]["data"]
        assert payload["type"]["name"] == "Blocks"

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_custom_link_type(self, mock_request):
        mock_request.return_value = {}

        create_issue_link("PRD-300", "PRD-299", link_type="Relates")

        payload = mock_request.call_args[1]["data"]
        assert payload["type"]["name"] == "Relates"

    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_API_TOKEN")
        with pytest.raises(EnvironmentError, match="ATLASSIAN_API_TOKEN"):
            create_issue_link("PRD-1", "PRD-2")


# ── JiraCreateIssueTool (CrewAI tool wrapper) ─────────────────────────


class TestJiraCreateIssueTool:

    def test_tool_metadata(self):
        tool = JiraCreateIssueTool()
        assert tool.name == "jira_create_issue"
        assert "Jira" in tool.description

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_success(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-42",
            "issue_id": "4242",
            "url": "https://example.atlassian.net/browse/PRD-42",
        }

        tool = JiraCreateIssueTool()
        result = tool._run(summary="Test Story")

        assert "PRD-42" in result
        assert "created" in result

    def test_run_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)

        tool = JiraCreateIssueTool()
        result = tool._run(summary="Fail")

        assert "skipped" in result

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_api_error(self, mock_create):
        mock_create.side_effect = RuntimeError("Jira API error 403")

        tool = JiraCreateIssueTool()
        result = tool._run(summary="ForbiddenStory")

        assert "failed" in result

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_labels_parsed(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-99",
            "issue_id": "9999",
            "url": "https://example.atlassian.net/browse/PRD-99",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="Labeled", labels="prd, auto-gen, review")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["labels"] == ["prd", "auto-gen", "review"]

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_empty_labels(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-98",
            "issue_id": "9898",
            "url": "https://example.atlassian.net/browse/PRD-98",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="No Labels", labels="")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["labels"] == []

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_passes_confluence_url(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-110",
            "issue_id": "11010",
            "url": "https://example.atlassian.net/browse/PRD-110",
        }

        tool = JiraCreateIssueTool()
        tool._run(
            summary="With Confluence",
            confluence_url="https://wiki.example.com/page/1",
        )

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["confluence_url"] == "https://wiki.example.com/page/1"

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_passes_component(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-111",
            "issue_id": "11111",
            "url": "https://example.atlassian.net/browse/PRD-111",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="UX Story", component="UX")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["component"] == "UX"

    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_parent_key_overrides_epic_key(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-112",
            "issue_id": "11212",
            "url": "https://example.atlassian.net/browse/PRD-112",
        }

        tool = JiraCreateIssueTool()
        tool._run(
            summary="Sub-task",
            issue_type="Task",
            epic_key="PRD-100",
            parent_key="PRD-105",
        )

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["epic_key"] == "PRD-105"

    @patch("crewai_productfeature_planner.tools.jira._operations.create_issue_link")
    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_creates_blocks_link(self, mock_create, mock_link):
        mock_create.return_value = {
            "issue_key": "PRD-113",
            "issue_id": "11313",
            "url": "https://example.atlassian.net/browse/PRD-113",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="Blocker", blocks_key="PRD-200")

        mock_link.assert_called_once_with(
            inward_issue_key="PRD-200",
            outward_issue_key="PRD-113",
            link_type="Blocks",
        )

    @patch("crewai_productfeature_planner.tools.jira._operations.create_issue_link")
    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_creates_is_blocked_by_link(self, mock_create, mock_link):
        mock_create.return_value = {
            "issue_key": "PRD-114",
            "issue_id": "11414",
            "url": "https://example.atlassian.net/browse/PRD-114",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="Blocked", is_blocked_by_key="PRD-113")

        mock_link.assert_called_once_with(
            inward_issue_key="PRD-114",
            outward_issue_key="PRD-113",
            link_type="Blocks",
        )

    @patch("crewai_productfeature_planner.tools.jira._operations.create_issue_link")
    @patch("crewai_productfeature_planner.tools.jira._operations.create_jira_issue")
    def test_run_link_failure_does_not_fail_issue(self, mock_create, mock_link):
        """Link creation failure should be logged but not fail the tool."""
        mock_create.return_value = {
            "issue_key": "PRD-115",
            "issue_id": "11515",
            "url": "https://example.atlassian.net/browse/PRD-115",
        }
        mock_link.side_effect = RuntimeError("Link API error")

        tool = JiraCreateIssueTool()
        result = tool._run(summary="Resilient", blocks_key="PRD-999")

        assert "created" in result
        assert "PRD-115" in result


# ── _strip_emails ────────────────────────────────────────────────────


class TestStripEmails:
    """Tests for _strip_emails helper."""

    def test_strips_single_email(self):
        assert _strip_emails("Contact user@example.com for details") == \
            "Contact [redacted] for details"

    def test_strips_multiple_emails(self):
        text = "From admin@corp.io to dev@corp.io"
        result = _strip_emails(text)
        assert "@" not in result
        assert "[redacted]" in result

    def test_preserves_text_without_emails(self):
        text = "No emails here, just plain text."
        assert _strip_emails(text) == text

    def test_strips_email_with_dots(self):
        result = _strip_emails("john.doe@my-company.co.uk sent this")
        assert "@" not in result

    def test_empty_string(self):
        assert _strip_emails("") == ""


# ── _markdown_to_wiki ────────────────────────────────────────────────


class TestMarkdownToWiki:
    """Tests for _markdown_to_wiki helper — Markdown→Jira wiki markup."""

    def test_h1_heading(self):
        assert _markdown_to_wiki("# Title") == "h1. Title"

    def test_h2_heading(self):
        assert _markdown_to_wiki("## Section") == "h2. Section"

    def test_h3_heading(self):
        assert _markdown_to_wiki("### Subsection") == "h3. Subsection"

    def test_bold(self):
        assert _markdown_to_wiki("This is **bold** text") == "This is *bold* text"

    def test_inline_code(self):
        assert _markdown_to_wiki("Use `my_func()`") == "Use {{my_func()}}"

    def test_link(self):
        assert _markdown_to_wiki("[Click here](https://example.com)") == \
            "[Click here|https://example.com]"

    def test_unordered_list(self):
        assert _markdown_to_wiki("- Item one") == "* Item one"

    def test_nested_list(self):
        assert _markdown_to_wiki("  - Nested") == "** Nested"

    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        result = _markdown_to_wiki(md)
        assert "{code:python}" in result
        assert "print('hello')" in result
        assert "{code}" in result

    def test_fenced_code_block_no_lang(self):
        md = "```\nsome code\n```"
        result = _markdown_to_wiki(md)
        assert result.startswith("{code}")
        assert "some code" in result

    def test_preserves_plain_text(self):
        assert _markdown_to_wiki("Just plain text.") == "Just plain text."

    def test_combined_formatting(self):
        md = "## Heading\n\n**Bold** and `code`\n\n- Item"
        result = _markdown_to_wiki(md)
        assert "h2. Heading" in result
        assert "*Bold*" in result
        assert "{{code}}" in result
        assert "* Item" in result

    def test_empty_string(self):
        assert _markdown_to_wiki("") == ""


# ── _inline_marks ────────────────────────────────────────────────────


class TestInlineMarks:
    """Tests for _inline_marks helper — inline Markdown → ADF text nodes."""

    def test_plain_text(self):
        nodes = _inline_marks("Hello world")
        assert len(nodes) == 1
        assert nodes[0] == {"type": "text", "text": "Hello world"}

    def test_bold(self):
        nodes = _inline_marks("This is **bold** text")
        assert any(
            n.get("marks") == [{"type": "strong"}] and n["text"] == "bold"
            for n in nodes
        )

    def test_inline_code(self):
        nodes = _inline_marks("Use `my_func()`")
        assert any(
            n.get("marks") == [{"type": "code"}] and n["text"] == "my_func()"
            for n in nodes
        )

    def test_link(self):
        nodes = _inline_marks("[Click](https://example.com)")
        assert any(
            n.get("marks") == [{"type": "link", "attrs": {"href": "https://example.com"}}]
            and n["text"] == "Click"
            for n in nodes
        )

    def test_mixed_formatting(self):
        nodes = _inline_marks("Start **bold** mid `code` end")
        texts = [n["text"] for n in nodes]
        assert "bold" in texts
        assert "code" in texts


# ── _markdown_to_adf ────────────────────────────────────────────────


class TestMarkdownToAdf:
    """Tests for _markdown_to_adf — Markdown → Atlassian Document Format."""

    def test_returns_doc_structure(self):
        result = _markdown_to_adf("Hello")
        assert result["type"] == "doc"
        assert result["version"] == 1
        assert isinstance(result["content"], list)

    def test_plain_paragraph(self):
        result = _markdown_to_adf("Hello world")
        assert result["content"][0]["type"] == "paragraph"
        assert _adf_to_text(result) == "Hello world"

    def test_heading_h1(self):
        result = _markdown_to_adf("# Title")
        h = result["content"][0]
        assert h["type"] == "heading"
        assert h["attrs"]["level"] == 1
        assert _adf_to_text(h) == "Title"

    def test_heading_h3(self):
        result = _markdown_to_adf("### Subsection")
        h = result["content"][0]
        assert h["type"] == "heading"
        assert h["attrs"]["level"] == 3

    def test_unordered_list(self):
        result = _markdown_to_adf("- Item 1\n- Item 2")
        bl = result["content"][0]
        assert bl["type"] == "bulletList"
        assert len(bl["content"]) == 2
        assert bl["content"][0]["type"] == "listItem"
        assert _adf_to_text(bl["content"][0]) == "Item 1"

    def test_ordered_list(self):
        result = _markdown_to_adf("1. First\n2. Second")
        ol = result["content"][0]
        assert ol["type"] == "orderedList"
        assert len(ol["content"]) == 2

    def test_fenced_code_block_with_lang(self):
        md = "```python\nprint('hello')\n```"
        result = _markdown_to_adf(md)
        cb = [n for n in result["content"] if n["type"] == "codeBlock"]
        assert len(cb) == 1
        assert cb[0]["attrs"]["language"] == "python"
        assert _adf_to_text(cb[0]) == "print('hello')"

    def test_fenced_code_block_no_lang(self):
        md = "```\nsome code\n```"
        result = _markdown_to_adf(md)
        cb = [n for n in result["content"] if n["type"] == "codeBlock"]
        assert len(cb) == 1
        assert "attrs" not in cb[0]
        assert _adf_to_text(cb[0]) == "some code"

    def test_horizontal_rule(self):
        result = _markdown_to_adf("---")
        assert result["content"][0]["type"] == "rule"

    def test_bold_in_paragraph(self):
        result = _markdown_to_adf("Start **bold** end")
        para = result["content"][0]
        assert para["type"] == "paragraph"
        bold_nodes = [
            n for n in para["content"]
            if n.get("marks") == [{"type": "strong"}]
        ]
        assert len(bold_nodes) == 1
        assert bold_nodes[0]["text"] == "bold"

    def test_inline_code_in_paragraph(self):
        result = _markdown_to_adf("Use `my_func()`")
        para = result["content"][0]
        code_nodes = [
            n for n in para["content"]
            if n.get("marks") == [{"type": "code"}]
        ]
        assert len(code_nodes) == 1
        assert code_nodes[0]["text"] == "my_func()"

    def test_empty_string(self):
        result = _markdown_to_adf("")
        assert result["type"] == "doc"
        assert result["version"] == 1
        assert len(result["content"]) >= 1

    def test_combined_document(self):
        md = "# Title\n\nSome **bold** text\n\n- Item 1\n- Item 2\n\n```json\n{}\n```"
        result = _markdown_to_adf(md)
        types = [n["type"] for n in result["content"]]
        assert "heading" in types
        assert "paragraph" in types
        assert "bulletList" in types
        assert "codeBlock" in types

    def test_multi_line_paragraph(self):
        result = _markdown_to_adf("Line 1\nLine 2")
        para = result["content"][0]
        assert para["type"] == "paragraph"
        # Should have hardBreak between lines
        has_break = any(n.get("type") == "hardBreak" for n in para["content"])
        assert has_break
        assert _adf_to_text(result) == "Line 1\nLine 2"

    def test_valid_json_serialisable(self):
        """ADF output must be JSON-serialisable for the Jira API."""
        md = "# H\n\n**Bold** `code`\n\n- A\n- B\n\n```py\nx=1\n```\n\n---"
        result = _markdown_to_adf(md)
        serialised = json.dumps(result)
        assert isinstance(serialised, str)


# ── create_jira_issue email sanitisation ─────────────────────────────


class TestCreateJiraIssueEmailSanitisation:
    """Verify that create_jira_issue strips emails from summary & description."""

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_strips_email_from_summary(self, mock_request):
        mock_request.return_value = {"key": "PRD-600", "id": "60600"}

        create_jira_issue(summary="Created by user@example.com")

        payload = mock_request.call_args[1]["data"]
        assert "@" not in payload["fields"]["summary"]
        assert "[redacted]" in payload["fields"]["summary"]

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_strips_email_from_description(self, mock_request):
        mock_request.return_value = {"key": "PRD-601", "id": "60601"}

        create_jira_issue(
            summary="Clean summary",
            description="Authored by admin@corp.io for review",
        )

        payload = mock_request.call_args[1]["data"]
        desc_text = _adf_to_text(payload["fields"]["description"])
        assert "@" not in desc_text
        assert "[redacted]" in desc_text

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_preserves_clean_summary(self, mock_request):
        mock_request.return_value = {"key": "PRD-602", "id": "60602"}

        create_jira_issue(summary="Add dark mode toggle")

        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["summary"] == "Add dark mode toggle"


# ── _normalize_priority ──────────────────────────────────────────────


class TestNormalizePriority:
    """Tests for the priority normaliser that sanitises LLM output."""

    def test_valid_name_passthrough(self):
        assert _normalize_priority("High") == "High"

    def test_case_insensitive(self):
        assert _normalize_priority("high") == "High"
        assert _normalize_priority("LOWEST") == "Lowest"

    def test_dict_unwrap(self):
        """LLM may pass {"name": "High"} — should unwrap."""
        assert _normalize_priority({"name": "High"}) == "High"

    def test_dict_with_id(self):
        assert _normalize_priority({"id": "Medium"}) == "Medium"

    def test_empty_returns_medium(self):
        assert _normalize_priority("") == "Medium"

    def test_none_returns_medium(self):
        assert _normalize_priority(None) == "Medium"

    def test_alias_critical(self):
        assert _normalize_priority("critical") == "Highest"

    def test_alias_blocker(self):
        assert _normalize_priority("blocker") == "Highest"

    def test_alias_normal(self):
        assert _normalize_priority("normal") == "Medium"

    def test_alias_minor(self):
        assert _normalize_priority("minor") == "Low"

    def test_alias_p2(self):
        assert _normalize_priority("P2") == "High"

    def test_unknown_defaults_to_medium(self):
        assert _normalize_priority("super-urgent") == "Medium"

    def test_strips_quotes(self):
        assert _normalize_priority("'High'") == "High"
        assert _normalize_priority('"Low"') == "Low"


# ── _drop_rejected_fields ─────────────────────────────────────────────


class TestDropRejectedFields:
    """Tests for the 400-error field-stripping helper."""

    def test_drops_priority(self):
        fields = {
            "project": {"key": "CJT"},
            "summary": "Test",
            "issuetype": {"name": "Epic"},
            "priority": {"name": "High"},
        }
        err = (
            'Jira API error 400: {"errorMessages":[],'
            '"errors":{"priority":"Specify the Priority (name) in the string format"}}'
        )
        dropped = _drop_rejected_fields(fields, err)
        assert dropped == ["priority"]
        assert "priority" not in fields

    def test_drops_components(self):
        fields = {
            "project": {"key": "CJT"},
            "summary": "Test",
            "issuetype": {"name": "Story"},
            "components": [{"name": "UX"}],
        }
        err = 'Jira API error 400: {"errorMessages":[],"errors":{"components":"Component/s is required."}}'
        dropped = _drop_rejected_fields(fields, err)
        assert dropped == ["components"]
        assert "components" not in fields

    def test_drops_labels(self):
        fields = {
            "project": {"key": "CJT"},
            "summary": "Test",
            "issuetype": {"name": "Story"},
            "labels": ["prd"],
        }
        err = 'Jira API error 400: {"errorMessages":[],"errors":{"labels":"Invalid label."}}'
        dropped = _drop_rejected_fields(fields, err)
        assert dropped == ["labels"]

    def test_does_not_drop_required_fields(self):
        """Fields like 'parent' or 'summary' must NOT be silently dropped."""
        fields = {
            "project": {"key": "CJT"},
            "summary": "Test",
            "issuetype": {"name": "Epic"},
            "parent": {"key": "CJT-999"},
        }
        err = 'Jira API error 400: {"errorMessages":[],"errors":{"parent":"Could not find issue."}}'
        dropped = _drop_rejected_fields(fields, err)
        assert dropped == []
        assert "parent" in fields  # NOT removed

    def test_no_json_returns_empty(self):
        fields = {"summary": "Test"}
        dropped = _drop_rejected_fields(fields, "Jira API error 400: connection reset")
        assert dropped == []

    def test_malformed_json_returns_empty(self):
        fields = {"summary": "Test"}
        dropped = _drop_rejected_fields(fields, "Jira API error 400: {not valid json")
        assert dropped == []

    def test_multiple_fields_dropped(self):
        fields = {
            "project": {"key": "CJT"},
            "summary": "Test",
            "issuetype": {"name": "Story"},
            "priority": {"name": "High"},
            "components": [{"name": "UX"}],
        }
        err = (
            'Jira API error 400: {"errorMessages":[],'
            '"errors":{"priority":"bad","components":"bad"}}'
        )
        dropped = _drop_rejected_fields(fields, err)
        assert set(dropped) == {"priority", "components"}
        assert "priority" not in fields
        assert "components" not in fields

    def test_field_not_in_payload_ignored(self):
        """If error mentions a field not in the payload, ignore it."""
        fields = {"project": {"key": "CJT"}, "summary": "Test"}
        err = 'Jira API error 400: {"errorMessages":[],"errors":{"priority":"bad"}}'
        dropped = _drop_rejected_fields(fields, err)
        assert dropped == []


# ── create_jira_issue retry-on-400 ────────────────────────────────────


class TestCreateJiraIssueRetry:
    """Verify that create_jira_issue retries after dropping rejected fields."""

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "CJT")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        # Pre-populate as empty so _fetch_priority_scheme() is not called
        # (empty dict = scheme unavailable → falls back to {"name": ...}).
        _jira_helpers_mod._priority_id_cache = {}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_retries_without_priority_on_400(self, mock_request):
        """When priority is rejected, retry without it and succeed."""
        err_body = '{"errorMessages":[],"errors":{"priority":"Specify the Priority (name) in the string format"}}'
        mock_request.side_effect = [
            RuntimeError(f"Jira API error 400: {err_body}"),
            {"key": "CJT-10", "id": "1010"},
        ]

        result = create_jira_issue(
            summary="Epic Test",
            issue_type="Epic",
            priority="High",
        )

        assert result["issue_key"] == "CJT-10"
        assert mock_request.call_count == 2
        # Second call should not have priority field
        retry_payload = mock_request.call_args_list[1][1]["data"]
        assert "priority" not in retry_payload["fields"]

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_retries_without_components_on_400(self, mock_request):
        err_body = '{"errorMessages":[],"errors":{"components":"Component does not exist."}}'
        mock_request.side_effect = [
            RuntimeError(f"Jira API error 400: {err_body}"),
            {"key": "CJT-11", "id": "1111"},
        ]

        result = create_jira_issue(
            summary="Story",
            component="NonExistent",
        )

        assert result["issue_key"] == "CJT-11"
        assert mock_request.call_count == 2
        retry_payload = mock_request.call_args_list[1][1]["data"]
        assert "components" not in retry_payload["fields"]

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_no_retry_on_non_retryable_field(self, mock_request):
        """If the rejected field is not in the allow-list, raise immediately."""
        err_body = '{"errorMessages":[],"errors":{"parent":"Could not find issue."}}'
        mock_request.side_effect = RuntimeError(f"Jira API error 400: {err_body}")

        with pytest.raises(RuntimeError, match="400"):
            create_jira_issue(
                summary="Bad parent",
                epic_key="MISSING-999",
            )

        assert mock_request.call_count == 1

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_no_retry_on_403(self, mock_request):
        """Non-400 errors should propagate immediately."""
        mock_request.side_effect = RuntimeError("Jira API error 403")

        with pytest.raises(RuntimeError, match="403"):
            create_jira_issue(summary="Forbidden")

        assert mock_request.call_count == 1

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_retry_fails_propagates_second_error(self, mock_request):
        """If the retry also fails, propagate the second error."""
        err_body = '{"errorMessages":[],"errors":{"priority":"bad"}}'
        mock_request.side_effect = [
            RuntimeError(f"Jira API error 400: {err_body}"),
            RuntimeError("Jira API error 400: some other error"),
        ]

        with pytest.raises(RuntimeError, match="some other error"):
            create_jira_issue(summary="Retry fails too", priority="Bad")

        assert mock_request.call_count == 2


# ── _run_id_label ────────────────────────────────────────────────────


class TestRunIdLabel:

    def test_basic(self):
        assert _run_id_label("abc123") == "prd-run-abc123"

    def test_strips_whitespace(self):
        assert _run_id_label("  abc ") == "prd-run-abc"

    def test_replaces_spaces(self):
        assert _run_id_label("my run id") == "prd-run-my-run-id"


# ── search_jira_issues ──────────────────────────────────────────────


class TestSearchJiraIssues:

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

    def test_empty_run_id(self):
        assert search_jira_issues("") == []

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_returns_issues(self, mock_request):
        mock_request.return_value = {
            "issues": [
                {
                    "key": "PRD-1",
                    "fields": {
                        "summary": "Epic title",
                        "issuetype": {"name": "Epic"},
                    },
                },
            ],
        }

        result = search_jira_issues("run-1", issue_type="Epic")

        assert len(result) == 1
        assert result[0]["issue_key"] == "PRD-1"
        assert result[0]["issue_type"] == "Epic"
        # Verify JQL includes label
        call_url = mock_request.call_args[0][1]
        assert "prd-run-run-1" in call_url

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_uses_v3_search_endpoint(self, mock_request):
        """Search must use /rest/api/3/search/jql (not deprecated v2)."""
        mock_request.return_value = {"issues": []}

        search_jira_issues("run-1")

        call_url = mock_request.call_args[0][1]
        assert "/rest/api/3/search/jql?" in call_url
        assert "/rest/api/2/" not in call_url

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_returns_empty_on_failure(self, mock_request):
        mock_request.side_effect = RuntimeError("API error 500")

        result = search_jira_issues("run-1")

        assert result == []


# ── create_jira_issue deduplication ──────────────────────────────────


class TestCreateJiraIssueDedup:
    """Tests for the duplicate detection in create_jira_issue."""

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        _jira_helpers_mod._priority_id_cache = {}

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_reuses_existing_epic(self, mock_request):
        """When an Epic already exists for this run_id, reuse it."""
        mock_request.return_value = {
            "issues": [
                {
                    "key": "PRD-42",
                    "fields": {
                        "summary": "Old Epic",
                        "issuetype": {"name": "Epic"},
                    },
                },
            ],
        }

        result = create_jira_issue(
            summary="New Epic",
            issue_type="Epic",
            run_id="run-1",
        )

        assert result["issue_key"] == "PRD-42"
        assert result.get("reused") is True
        # Only the search call — no POST
        mock_request.assert_called_once()

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_reuses_existing_story_by_summary(self, mock_request):
        """Story dedup matches on summary (case-insensitive)."""
        mock_request.side_effect = [
            {
                "issues": [
                    {
                        "key": "PRD-50",
                        "fields": {
                            "summary": "[UX] Design onboarding",
                            "issuetype": {"name": "Story"},
                        },
                    },
                ],
            },
        ]

        result = create_jira_issue(
            summary="[UX] Design onboarding",
            issue_type="Story",
            run_id="run-1",
        )

        assert result["issue_key"] == "PRD-50"
        assert result.get("reused") is True

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_creates_new_story_when_summary_differs(self, mock_request):
        """Story with different summary should create a new one."""
        mock_request.side_effect = [
            {
                "issues": [
                    {
                        "key": "PRD-50",
                        "fields": {
                            "summary": "[UX] Design onboarding",
                            "issuetype": {"name": "Story"},
                        },
                    },
                ],
            },
            {"key": "PRD-51", "id": "5151"},
        ]

        result = create_jira_issue(
            summary="[Engineering] Implement backend",
            issue_type="Story",
            run_id="run-1",
        )

        assert result["issue_key"] == "PRD-51"
        assert result.get("reused") is None
        assert mock_request.call_count == 2  # search + create

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_no_dedup_without_run_id(self, mock_request):
        """Without run_id, should create directly — no search."""
        mock_request.return_value = {"key": "PRD-99", "id": "9999"}

        result = create_jira_issue(
            summary="No run ID story",
            issue_type="Story",
        )

        assert result["issue_key"] == "PRD-99"
        mock_request.assert_called_once()

    @patch("crewai_productfeature_planner.tools.jira._http._jira_request")
    def test_run_id_label_auto_attached(self, mock_request):
        """run_id should auto-add a prd-run-X label."""
        mock_request.side_effect = [
            {"issues": []},
            {"key": "PRD-60", "id": "6060"},
        ]

        create_jira_issue(
            summary="Labelled story",
            run_id="abc-123",
        )

        payload = mock_request.call_args_list[1][1]["data"]
        assert "prd-run-abc-123" in payload["fields"]["labels"]


# ── Context-variable override tests ─────────────────────────────────


class TestJiraContextVarOverrides:
    """Tests for the context-variable project key resolution mechanism."""

    @pytest.fixture(autouse=True)
    def _clean_context_var(self):
        """Ensure context var is clean for each test."""
        token = _project_key_ctx.set("")
        yield
        _project_key_ctx.reset(token)

    def test_context_var_overrides_env(self, monkeypatch):
        """Context-var project key should take priority over env var."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "ENV_KEY")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        token = set_jira_project_key("CTX_KEY")
        try:
            env = _get_jira_env()
            assert env["project_key"] == "CTX_KEY"
        finally:
            _project_key_ctx.reset(token)

    def test_explicit_param_overrides_context_var(self, monkeypatch):
        """Explicit project_key param should override context var."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "ENV")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        token = set_jira_project_key("CTX")
        try:
            env = _get_jira_env(project_key="EXPLICIT")
            assert env["project_key"] == "EXPLICIT"
        finally:
            _project_key_ctx.reset(token)

    def test_env_var_used_when_context_empty(self, monkeypatch):
        """Without context var, env var should be used."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "FROM_ENV")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_jira_env()
        assert env["project_key"] == "FROM_ENV"

    def test_jira_project_context_manager(self, monkeypatch):
        """Context manager should set and reset the project key."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "OLD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        with jira_project_context(project_key="NEW"):
            env = _get_jira_env()
            assert env["project_key"] == "NEW"

        # After context manager, should fallback to env
        env_after = _get_jira_env()
        assert env_after["project_key"] == "OLD"

    def test_context_manager_empty_string_ignored(self, monkeypatch):
        """Empty string should not override env var."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "KEEP")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        with jira_project_context(project_key=""):
            env = _get_jira_env()
            assert env["project_key"] == "KEEP"
