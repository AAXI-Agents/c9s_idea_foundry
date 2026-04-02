"""Pydantic models for PRD flow API requests and domain objects.

This module is a backward-compatible re-export facade.  All symbols are
defined in focused sub-modules and re-exported here so that existing
``from ...apis.prd.models import X`` statements continue to work.
"""

# Section constants
from ._sections import SECTION_KEYS, SECTION_ORDER

# Agent constants and helper
from ._agents import (
    AGENT_GEMINI,
    AGENT_OPENAI,
    DEFAULT_AGENT_FALLBACK,
    VALID_AGENTS,
    get_default_agent,
)

# Core domain models
from ._domain import (
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
    PRDDraft,
    PRDSection,
)

# API request models
from ._requests import (
    PRDApproveRequest,
    PRDKickoffRequest,
    PRDPauseRequest,
    PRDResumeRequest,
)

# API response models
from ._responses import (
    ActivityEvent,
    ActivityLogResponse,
    PRDActionResponse,
    PRDDraftDetail,
    PRDKickoffResponse,
    PRDResumableListResponse,
    PRDResumableRun,
    PRDResumeResponse,
    PRDRunStatusResponse,
    PRDSectionDetail,
)

# Job tracking models
from ._jobs import JobDetail, JobListResponse

# Error model
from ._errors import ErrorResponse

__all__ = [
    "SECTION_ORDER",
    "SECTION_KEYS",
    "AGENT_OPENAI",
    "AGENT_GEMINI",
    "VALID_AGENTS",
    "DEFAULT_AGENT_FALLBACK",
    "get_default_agent",
    "ExecutiveSummaryIteration",
    "ExecutiveSummaryDraft",
    "PRDSection",
    "PRDDraft",
    "PRDKickoffRequest",
    "PRDApproveRequest",
    "PRDPauseRequest",
    "PRDResumeRequest",
    "PRDKickoffResponse",
    "PRDActionResponse",
    "PRDSectionDetail",
    "PRDDraftDetail",
    "PRDRunStatusResponse",
    "PRDResumableRun",
    "PRDResumableListResponse",
    "PRDResumeResponse",
    "JobDetail",
    "JobListResponse",
    "ErrorResponse",
]
