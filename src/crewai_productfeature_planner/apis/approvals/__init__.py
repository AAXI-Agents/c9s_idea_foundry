"""Approvals API — cross-project pending approvals queue.

Provides ``GET /approvals/pending`` for listing items the user can
act on across all their accessible projects.
"""

from crewai_productfeature_planner.apis.approvals.router import router

__all__ = ["router"]
