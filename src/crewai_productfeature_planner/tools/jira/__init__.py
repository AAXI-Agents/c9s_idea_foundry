"""Atlassian Jira ticket creation tool — public API re-exports.

This package provides all the same names that were previously in
``jira_tool.py``, split across focused sub-modules:

- ``_config``     — environment, context variables, auth
- ``_http``       — low-level HTTP transport
- ``_helpers``    — text conversion, field helpers, priority resolution
- ``_operations`` — issue CRUD (search, create, link)
- ``_tool``       — CrewAI ``BaseTool`` wrapper
"""

from crewai_productfeature_planner.tools.jira._config import (
    _build_auth_header,
    _get_jira_env,
    _has_jira_credentials,
    _project_key_ctx,
    jira_project_context,
    set_jira_project_key,
)
from crewai_productfeature_planner.tools.jira._helpers import (
    _JIRA_PRIORITIES,
    _RETRYABLE_FIELDS,
    _drop_rejected_fields,
    _fetch_priority_scheme,
    _normalize_priority,
    _priority_id_cache,
    _resolve_priority_field,
    _run_id_label,
    _markdown_to_wiki,
    _strip_emails,
)
from crewai_productfeature_planner.tools.jira._http import _jira_request
from crewai_productfeature_planner.tools.jira._operations import (
    create_issue_link,
    create_jira_issue,
    search_jira_issues,
)
from crewai_productfeature_planner.tools.jira._tool import (
    JiraCreateIssueInput,
    JiraCreateIssueTool,
)

__all__ = [
    # _config
    "_project_key_ctx",
    "set_jira_project_key",
    "jira_project_context",
    "_get_jira_env",
    "_has_jira_credentials",
    "_build_auth_header",
    # _http
    "_jira_request",
    # _helpers
    "_strip_emails",
    "_markdown_to_wiki",
    "_RETRYABLE_FIELDS",
    "_drop_rejected_fields",
    "_JIRA_PRIORITIES",
    "_priority_id_cache",
    "_fetch_priority_scheme",
    "_normalize_priority",
    "_resolve_priority_field",
    "_run_id_label",
    # _operations
    "search_jira_issues",
    "create_jira_issue",
    "create_issue_link",
    # _tool
    "JiraCreateIssueInput",
    "JiraCreateIssueTool",
]
