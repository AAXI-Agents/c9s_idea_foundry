"""Pydantic models for Agent Worker proxy endpoints.

Frontend-facing models accept the frontend's field names.
Internal mapping translates to Agent Worker's field names before forwarding.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Atlassian Credentials ─────────────────────────────────────


class AtlassianCredentialRequest(BaseModel):
    """Frontend sends this to upsert Atlassian credentials.

    Field names match the frontend convention (``jira_`` prefix).
    The proxy normalises to Agent Worker names before forwarding.
    """

    jira_base_url: str = Field(
        ..., min_length=1, description="Base URL, e.g. https://mysite.atlassian.net",
    )
    jira_email: str = Field(
        ..., min_length=1, description="Atlassian account email.",
    )
    jira_api_token: str = Field(
        ..., min_length=1, description="Atlassian API token.",
    )
    confluence_base_url: str | None = Field(
        default=None,
        description="Optional separate Confluence base URL. Defaults to jira_base_url.",
    )
    organization_id: str | None = Field(
        default=None,
        description="Organization ID for multi-tenant scoping.",
    )

    def to_agent_worker_payload(self) -> dict:
        """Map frontend field names → Agent Worker field names."""
        payload: dict = {
            "base_url": self.jira_base_url,
            "username": self.jira_email,
            "api_token": self.jira_api_token,
        }
        if self.organization_id:
            payload["organization_id"] = self.organization_id
        if self.confluence_base_url:
            payload["confluence_base_url"] = self.confluence_base_url
        return payload


class AtlassianCredentialTestResult(BaseModel):
    """Response from testing Atlassian credentials."""

    success: bool = Field(..., description="Overall test passed.")
    message: str = Field(default="", description="Human-readable result.")
    jira_valid: bool = Field(default=False, description="Jira auth valid.")
    confluence_valid: bool = Field(default=False, description="Confluence auth valid.")


class AtlassianCredentialStatusResponse(BaseModel):
    """Response after upserting credentials."""

    saved: bool = Field(..., description="Credentials saved locally.")
    synced_to_agent_worker: bool = Field(
        ..., description="Credentials forwarded to Agent Worker.",
    )
    message: str = Field(default="", description="Human-readable status.")
