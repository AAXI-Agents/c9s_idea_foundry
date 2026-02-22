"""Tests for the AgentOrchestrator and AgentStage core classes."""

import pytest

from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    AgentStage,
    StageResult,
)


# ── StageResult ──────────────────────────────────────────────────────


class TestStageResult:
    """Tests for the StageResult dataclass."""

    def test_stage_result_creation(self):
        result = StageResult(output="hello", history=[{"iteration": 1}])
        assert result.output == "hello"
        assert result.history == [{"iteration": 1}]

    def test_stage_result_defaults(self):
        result = StageResult(output="hello")
        assert result.history == []

    def test_stage_result_frozen(self):
        result = StageResult(output="hello")
        with pytest.raises(AttributeError):
            result.output = "world"


# ── AgentStage ───────────────────────────────────────────────────────


def _make_stage(
    name="test_stage",
    run_result=None,
    should_skip=False,
    get_approval=None,
    finalized_exc=None,
    requires_approval=None,
):
    """Helper to build a simple AgentStage for tests."""
    applied_results = []

    return AgentStage(
        name=name,
        description=f"Test stage: {name}",
        run=lambda: run_result or StageResult(output="default_output"),
        should_skip=lambda: should_skip,
        apply=lambda r: applied_results.append(r),
        get_approval=get_approval,
        finalized_exc=finalized_exc,
        requires_approval=requires_approval,
    ), applied_results


class TestAgentStage:
    """Tests for the AgentStage dataclass."""

    def test_stage_fields(self):
        stage, _ = _make_stage(name="my_stage")
        assert stage.name == "my_stage"
        assert stage.description == "Test stage: my_stage"
        assert stage.get_approval is None
        assert stage.finalized_exc is None
        assert stage.requires_approval is None

    def test_stage_run_returns_result(self):
        result = StageResult(output="test_output", history=[{"i": 1}])
        stage, _ = _make_stage(run_result=result)
        assert stage.run() == result

    def test_stage_should_skip(self):
        stage_skip, _ = _make_stage(should_skip=True)
        stage_run, _ = _make_stage(should_skip=False)
        assert stage_skip.should_skip() is True
        assert stage_run.should_skip() is False

    def test_stage_apply(self):
        result = StageResult(output="applied")
        stage, applied = _make_stage()
        stage.apply(result)
        assert applied == [result]


# ── AgentOrchestrator ────────────────────────────────────────────────


class TestAgentOrchestrator:
    """Tests for the AgentOrchestrator pipeline engine."""

    def test_empty_pipeline(self):
        orch = AgentOrchestrator()
        assert orch.stages == []
        assert orch.completed == []
        assert orch.skipped == []
        assert orch.failed == []
        orch.run_pipeline()  # should not raise

    def test_register_returns_self(self):
        orch = AgentOrchestrator()
        stage, _ = _make_stage()
        ret = orch.register(stage)
        assert ret is orch

    def test_register_chaining(self):
        orch = AgentOrchestrator()
        s1, _ = _make_stage(name="a")
        s2, _ = _make_stage(name="b")
        orch.register(s1).register(s2)
        assert len(orch.stages) == 2
        assert [s.name for s in orch.stages] == ["a", "b"]

    def test_stages_returns_copy(self):
        orch = AgentOrchestrator()
        stage, _ = _make_stage()
        orch.register(stage)
        stages = orch.stages
        stages.clear()
        assert len(orch.stages) == 1  # original unmodified

    def test_single_stage_completes(self):
        result = StageResult(output="done")
        stage, applied = _make_stage(run_result=result)
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()

        assert orch.completed == ["test_stage"]
        assert orch.skipped == []
        assert orch.failed == []
        assert applied == [result]

    def test_stage_skipped(self):
        stage, applied = _make_stage(should_skip=True)
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()

        assert orch.skipped == ["test_stage"]
        assert orch.completed == []
        assert orch.failed == []
        assert applied == []  # apply never called

    def test_stage_failure_continues_pipeline(self):
        """A failed stage is logged and the pipeline continues."""
        def _boom():
            raise RuntimeError("LLM unavailable")

        failing_stage = AgentStage(
            name="failing",
            description="Will fail",
            run=_boom,
            should_skip=lambda: False,
            apply=lambda r: None,
        )
        ok_result = StageResult(output="ok")
        ok_stage, applied = _make_stage(name="ok_stage", run_result=ok_result)

        orch = AgentOrchestrator()
        orch.register(failing_stage).register(ok_stage)
        orch.run_pipeline()

        assert orch.failed == ["failing"]
        assert orch.completed == ["ok_stage"]
        assert applied == [ok_result]

    def test_multiple_stages_run_in_order(self):
        """Stages execute in registration order."""
        order = []
        results = []

        def _make_ordered(name, idx):
            result = StageResult(output=f"output_{idx}")
            return AgentStage(
                name=name,
                description=name,
                run=lambda i=idx, r=result: (order.append(i), r)[1],
                should_skip=lambda: False,
                apply=lambda r: results.append(r),
            )

        orch = AgentOrchestrator()
        orch.register(_make_ordered("first", 1))
        orch.register(_make_ordered("second", 2))
        orch.register(_make_ordered("third", 3))
        orch.run_pipeline()

        assert order == [1, 2, 3]
        assert orch.completed == ["first", "second", "third"]

    def test_mixed_skip_and_complete(self):
        s1, a1 = _make_stage(name="runs", should_skip=False)
        s2, a2 = _make_stage(name="skips", should_skip=True)
        s3, a3 = _make_stage(name="also_runs", should_skip=False)

        orch = AgentOrchestrator()
        orch.register(s1).register(s2).register(s3)
        orch.run_pipeline()

        assert orch.completed == ["runs", "also_runs"]
        assert orch.skipped == ["skips"]
        assert len(a1) == 1
        assert len(a2) == 0
        assert len(a3) == 1


# ── Approval gate ────────────────────────────────────────────────────


class FinalizeEarly(Exception):
    """Test-only exception for early finalization."""


class TestApprovalGate:
    """Tests for the orchestrator's approval gate mechanism."""

    def test_approval_gate_finalizes(self):
        """When get_approval returns True, finalized_exc is raised."""
        stage, _ = _make_stage(
            get_approval=lambda: True,
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: True,
        )
        orch = AgentOrchestrator()
        orch.register(stage)

        with pytest.raises(FinalizeEarly):
            orch.run_pipeline()

        assert orch.completed == ["test_stage"]

    def test_approval_gate_continues_on_false(self):
        """When get_approval returns False, pipeline continues."""
        stage, _ = _make_stage(
            get_approval=lambda: False,
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: True,
        )
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()

        assert orch.completed == ["test_stage"]

    def test_approval_gate_skipped_when_requires_false(self):
        """Gate should not fire when requires_approval returns False."""
        gate_called = False

        def _gate():
            nonlocal gate_called
            gate_called = True
            return True

        stage, _ = _make_stage(
            get_approval=_gate,
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: False,  # not required
        )
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()

        assert gate_called is False

    def test_approval_gate_skipped_when_no_callback(self):
        """Gate should not fire when get_approval is None."""
        stage, _ = _make_stage(
            get_approval=None,  # no callback
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: True,
        )
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()  # should not raise

    def test_approval_gate_skipped_when_requires_none(self):
        """Gate should not fire when requires_approval is None."""
        stage, _ = _make_stage(
            get_approval=lambda: True,
            finalized_exc=FinalizeEarly,
            requires_approval=None,
        )
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()  # should not raise

    def test_approval_gate_fires_after_skip(self):
        """Approval gate should fire even when a stage is skipped
        (e.g. already done from a prior or resumed run)."""
        # Stage is skipped, but requires_approval returns True
        stage = AgentStage(
            name="already_done",
            description="Was done in a prior run",
            run=lambda: StageResult(output="x"),
            should_skip=lambda: True,  # skipped
            apply=lambda r: None,
            get_approval=lambda: True,
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: True,  # state says "done"
        )
        orch = AgentOrchestrator()
        orch.register(stage)

        with pytest.raises(FinalizeEarly):
            orch.run_pipeline()

        assert orch.skipped == ["already_done"]

    def test_approval_gate_not_fired_after_failure(self):
        """Approval gate should NOT fire when the stage failed."""
        gate_called = False

        def _gate():
            nonlocal gate_called
            gate_called = True
            return True

        stage = AgentStage(
            name="broken",
            description="Will fail",
            run=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            should_skip=lambda: False,
            apply=lambda r: None,
            get_approval=_gate,
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: True,
        )
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()

        assert orch.failed == ["broken"]
        assert gate_called is False

    def test_finalize_stops_pipeline(self):
        """Early finalization should prevent subsequent stages from running."""
        second_ran = False

        def _mark_second():
            nonlocal second_ran
            second_ran = True
            return StageResult(output="nope")

        s1, _ = _make_stage(
            name="finalizer",
            get_approval=lambda: True,
            finalized_exc=FinalizeEarly,
            requires_approval=lambda: True,
        )
        s2 = AgentStage(
            name="after",
            description="Should not run",
            run=_mark_second,
            should_skip=lambda: False,
            apply=lambda r: None,
        )
        orch = AgentOrchestrator()
        orch.register(s1).register(s2)

        with pytest.raises(FinalizeEarly):
            orch.run_pipeline()

        assert second_ran is False
        assert orch.completed == ["finalizer"]

    def test_no_finalized_exc_means_no_raise(self):
        """When finalized_exc is None, approval=True is a no-op."""
        stage, _ = _make_stage(
            get_approval=lambda: True,
            finalized_exc=None,  # no exception to raise
            requires_approval=lambda: True,
        )
        orch = AgentOrchestrator()
        orch.register(stage)
        orch.run_pipeline()  # should not raise

        assert orch.completed == ["test_stage"]
