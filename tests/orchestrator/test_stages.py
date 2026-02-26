"""Backward-compatible re-export of orchestrator stage tests.

The tests that used to live in this single monolithic file have been
split into focused modules mirroring the source layout:

    test_helpers.py           credential checks, _print_delivery_status
    test_idea_refinement.py   TestIdeaRefinementStage
    test_requirements.py      TestRequirementsBreakdownStage
    test_confluence.py        TestConfluencePublishStage
    test_jira.py              TestExtractIssueKeys, TestJiraTicketingStage
    test_pipelines.py         TestBuildDefaultPipeline, TestBuildPostCompletionPipeline
    test_post_completion.py   TestBuildPostCompletionCrew
    test_startup_review.py    TestDiscoverPublishablePrds, TestStartupMarkdownReviewStage,
                              TestStartupPipeline
    test_startup_delivery.py  TestDiscoverPendingDeliveries, TestBuildStartupDeliveryCrew

This file verifies that the ``stages`` re-export facade can still be
imported without errors.
"""

from crewai_productfeature_planner.orchestrator.stages import (  # noqa: F401
    _discover_pending_deliveries,
    _discover_publishable_prds,
    _extract_issue_keys,
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    _print_delivery_status,
    build_confluence_publish_stage,
    build_default_pipeline,
    build_idea_refinement_stage,
    build_jira_ticketing_stage,
    build_post_completion_crew,
    build_post_completion_pipeline,
    build_requirements_breakdown_stage,
    build_startup_delivery_crew,
    build_startup_markdown_review_stage,
    build_startup_pipeline,
    DeliveryItem,
)


class TestStagesFacadeImports:
    """Smoke test: every public name is importable from the facade."""

    def test_all_names_importable(self):
        assert callable(build_default_pipeline)
        assert callable(build_post_completion_crew)
        assert callable(_discover_pending_deliveries)
        assert callable(build_startup_delivery_crew)
        assert callable(build_startup_pipeline)
