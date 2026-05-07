"""Tests for knowledge context injection into the PRD flow pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.flows._constants import PRDState


class TestKnowledgeContextInjectionInPipeline:
    """Tests that knowledge context is injected at the right pipeline points."""

    @patch(
        "crewai_productfeature_planner.scripts.memory_loader.resolve_project_id",
        return_value="proj-abc",
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context.build_knowledge_context",
        return_value="## Project Knowledge Context\n\nTest context",
    )
    @patch(
        "crewai_productfeature_planner.agents.idea_manager.refine_idea",
        return_value=("Refined idea output", [{"iteration": 1}], []),
    )
    def test_idea_refinement_injects_knowledge_context(
        self, mock_refine, mock_ctx, mock_resolve
    ):
        """Idea refinement passes knowledge context to refine_idea."""
        from crewai_productfeature_planner.orchestrator._idea_refinement import (
            build_idea_refinement_stage,
        )

        # Create a mock flow with required state
        flow = MagicMock()
        flow.state = PRDState(
            run_id="run-123",
            idea="Build a payment system",
            idea_refined=False,
            knowledge_context="",
        )
        flow._tenant = None
        flow._idea_options_callback = None

        # Build and check skip
        with patch(
            "crewai_productfeature_planner.orchestrator._idea_refinement._has_gemini_credentials",
            return_value=True,
        ):
            stage = build_idea_refinement_stage(flow)
            assert not stage.should_skip()

            # Run the stage
            result = stage.run()

            # Verify knowledge context was built
            mock_ctx.assert_called_once_with("proj-abc", tenant=None)

            # Verify refine_idea received the enriched idea
            call_args = mock_refine.call_args
            assert "## Project Knowledge Context" in call_args[0][0]
            assert "Build a payment system" in call_args[0][0]

            # Verify state was updated
            assert flow.state.knowledge_context == "## Project Knowledge Context\n\nTest context"

    @patch(
        "crewai_productfeature_planner.scripts.memory_loader.resolve_project_id",
        return_value="proj-abc",
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context.build_knowledge_context",
        return_value="",
    )
    @patch(
        "crewai_productfeature_planner.agents.idea_manager.refine_idea",
        return_value=("Refined idea", [{"iteration": 1}], []),
    )
    def test_no_knowledge_passes_raw_idea(
        self, mock_refine, mock_ctx, mock_resolve
    ):
        """When no knowledge exists, raw idea is passed unchanged."""
        from crewai_productfeature_planner.orchestrator._idea_refinement import (
            build_idea_refinement_stage,
        )

        flow = MagicMock()
        flow.state = PRDState(
            run_id="run-123",
            idea="Build a payment system",
            idea_refined=False,
            knowledge_context="",
        )
        flow._tenant = None
        flow._idea_options_callback = None

        with patch(
            "crewai_productfeature_planner.orchestrator._idea_refinement._has_gemini_credentials",
            return_value=True,
        ):
            stage = build_idea_refinement_stage(flow)
            result = stage.run()

            # Raw idea passed without prefix
            call_args = mock_refine.call_args
            assert call_args[0][0] == "Build a payment system"

    @patch(
        "crewai_productfeature_planner.scripts.memory_loader.resolve_project_id",
        return_value="proj-abc",
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context.build_knowledge_context",
    )
    @patch(
        "crewai_productfeature_planner.agents.idea_manager.refine_idea",
        return_value=("Refined", [], []),
    )
    def test_existing_knowledge_context_not_refetched(
        self, mock_refine, mock_ctx, mock_resolve
    ):
        """If knowledge_context already set on state, don't re-fetch."""
        from crewai_productfeature_planner.orchestrator._idea_refinement import (
            build_idea_refinement_stage,
        )

        flow = MagicMock()
        flow.state = PRDState(
            run_id="run-123",
            idea="Build a payment system",
            idea_refined=False,
            knowledge_context="Already set context",
        )
        flow._tenant = None
        flow._idea_options_callback = None

        with patch(
            "crewai_productfeature_planner.orchestrator._idea_refinement._has_gemini_credentials",
            return_value=True,
        ):
            stage = build_idea_refinement_stage(flow)
            result = stage.run()

            # build_knowledge_context should not be called
            mock_ctx.assert_not_called()


class TestPRDStateKnowledgeField:
    """Tests that PRDState includes the knowledge_context field."""

    def test_default_empty(self):
        state = PRDState()
        assert state.knowledge_context == ""

    def test_can_set_value(self):
        state = PRDState(knowledge_context="Some context")
        assert state.knowledge_context == "Some context"

    def test_persists_in_dict(self):
        state = PRDState(knowledge_context="Test")
        data = state.model_dump()
        assert data["knowledge_context"] == "Test"
