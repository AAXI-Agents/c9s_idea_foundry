"""Core domain models for PRD drafts and executive summary iterations."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ._sections import SECTION_ORDER


def condensed_text(text: str, *, char_limit: int = 1500) -> str:
    """Truncate *text* to *char_limit* chars for LLM context.

    Used to shrink large specialist outputs (EPS, engineering plan)
    when full verbatim text isn't needed — e.g. the critique task
    only needs enough to judge consistency, not to write content.
    """
    if not text or len(text) <= char_limit:
        return text
    return text[:char_limit] + "\n[...truncated]"


class ExecutiveSummaryIteration(BaseModel):
    """A single iteration record for the executive summary phase."""

    content: str = Field(default="", description="Markdown content of this iteration.")
    iteration: int = Field(
        default=1, description="1-based iteration number."
    )
    critique: str | None = Field(
        default=None,
        description="Critique feedback from critique_prd_task, initially null.",
    )
    updated_date: str = Field(
        default="",
        description="ISO-8601 timestamp of this iteration.",
    )


class ExecutiveSummaryDraft(BaseModel):
    """Tracks the iterative executive summary produced in the draft phase."""

    iterations: list[ExecutiveSummaryIteration] = Field(default_factory=list)
    is_approved: bool = Field(
        default=False,
        description="Whether the executive summary has been approved.",
    )

    @property
    def latest(self) -> ExecutiveSummaryIteration | None:
        """Return the most recent iteration, or None if empty."""
        return self.iterations[-1] if self.iterations else None

    @property
    def latest_content(self) -> str:
        """Return the content of the most recent iteration."""
        latest = self.latest
        return latest.content if latest else ""

    @property
    def current_iteration(self) -> int:
        """Return the current iteration number (0 if none)."""
        latest = self.latest
        return latest.iteration if latest else 0


class PRDSection(BaseModel):
    """A single section of a PRD with its own iteration tracking."""

    key: str = Field(..., description="Section identifier slug.")
    title: str = Field(..., description="Human-readable section title.")
    step: int = Field(
        default=0,
        description="1-based step number indicating order in the PRD workflow.",
    )
    content: str = Field(default="", description="Markdown content of this section.")
    critique: str = Field(default="", description="Latest critique for this section.")
    iteration: int = Field(
        default=0, description="How many times this section has been iterated."
    )
    updated_date: str = Field(
        default="",
        description="ISO-8601 timestamp of the last update to this section.",
    )
    is_approved: bool = Field(
        default=False, description="Whether the user has approved this section."
    )
    agent_results: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Per-agent draft results for this section. Keys are provider "
            "identifiers (e.g. 'openai'), values are "
            "the markdown content each agent produced."
        ),
    )
    selected_agent: str = Field(
        default="",
        description=(
            "Which agent's result was selected by the user. Empty string "
            "means no selection has been made yet."
        ),
    )


class PRDDraft(BaseModel):
    """Structured PRD draft with individually iterable sections."""

    sections: list[PRDSection] = Field(default_factory=list)

    @classmethod
    def create_empty(cls) -> "PRDDraft":
        """Create a new PRDDraft with all sections initialized empty."""
        return cls(
            sections=[
                PRDSection(key=key, title=title, step=idx)
                for idx, (key, title) in enumerate(SECTION_ORDER, 1)
            ]
        )

    def get_section(self, key: str) -> PRDSection | None:
        """Look up a section by its key."""
        return next((s for s in self.sections if s.key == key), None)

    def approved_context(
        self, exclude_key: str = "", *, exclude_keys: set[str] | None = None,
    ) -> str:
        """Return markdown of all approved sections as context."""
        skip = {exclude_key} if exclude_key else set()
        if exclude_keys:
            skip |= exclude_keys
        parts = []
        for s in self.sections:
            if s.is_approved and s.key not in skip and s.content:
                parts.append(f"## {s.title}\n\n{s.content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def approved_context_condensed(
        self,
        exclude_key: str = "",
        *,
        exclude_keys: set[str] | None = None,
        char_limit: int = 500,
    ) -> str:
        """Like *approved_context* but truncates each section body.

        Used for the refine task (research model) to reduce prompt size
        while still giving the model enough context for consistency.
        """
        skip = {exclude_key} if exclude_key else set()
        if exclude_keys:
            skip |= exclude_keys
        parts = []
        for s in self.sections:
            if s.is_approved and s.key not in skip and s.content:
                body = s.content[:char_limit]
                if len(s.content) > char_limit:
                    body += "\n[...truncated]"
                parts.append(f"## {s.title}\n\n{body}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def all_sections_context(self, exclude_key: str = "") -> str:
        """Return markdown of all sections that have content, with status labels."""
        parts = []
        for s in self.sections:
            if s.key != exclude_key and s.content:
                status = "APPROVED" if s.is_approved else "DRAFT"
                parts.append(f"## {s.title} [{status}]\n\n{s.content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def all_approved(self) -> bool:
        """Check if all sections have been approved."""
        return all(s.is_approved for s in self.sections)

    def next_section(self) -> PRDSection | None:
        """Return the next section that hasn't been approved yet."""
        return next((s for s in self.sections if not s.is_approved), None)

    def assemble(self) -> str:
        """Assemble all sections into a single markdown PRD document."""
        from crewai_productfeature_planner.components.document import (
            sanitize_section_content,
        )

        parts = [
            f"## {sanitize_section_content(s.title, s.key)}\n\n"
            f"{sanitize_section_content(s.content, s.key)}"
            for s in self.sections
            if s.content
        ]
        return "# Product Requirements Document\n\n" + "\n\n---\n\n".join(parts)
