"""Core orchestrator classes for the agent pipeline.

This module provides the data structures and execution engine that
drive the agent workflow.  Individual stages are defined in
:mod:`crewai_productfeature_planner.orchestrator.stages`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


# ── Data ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageResult:
    """Immutable outcome produced by an agent stage's *run* callable.

    Attributes:
        output:   The primary text artefact (e.g. refined idea, requirements).
        history:  Per-iteration records for the stage.
        extra:    Optional dict for stage-specific data (e.g. options_history).
    """

    output: str
    history: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class AgentStage:
    """Declarative description of one step in the agent pipeline.

    Every field is a plain callable so stages can be assembled either
    from closures (see ``stages.py``) or from any other callable source.

    Attributes:
        name:               Unique slug, e.g. ``"idea_refinement"``.
        description:        Human-readable purpose shown in logs.
        run:                Execute the stage → :class:`StageResult`.
        should_skip:        Return ``True`` to skip (e.g. already done,
                            missing credentials).
        apply:              Persist a :class:`StageResult` into flow state.
        get_approval:       Optional — ask user/callback whether to
                            finalize early.  Return ``True`` to finalize.
        finalized_exc:      Exception class raised on early finalization.
        requires_approval:  Optional — return ``True`` when the approval
                            gate should fire (e.g. stage actually ran AND
                            a callback is wired).
    """

    name: str
    description: str
    run: Callable[[], StageResult]
    should_skip: Callable[[], bool]
    apply: Callable[[StageResult], None]
    get_approval: Optional[Callable[[], bool]] = None
    finalized_exc: Optional[type] = None
    requires_approval: Optional[Callable[[], bool]] = None


# ── Orchestrator ──────────────────────────────────────────────────────


class AgentOrchestrator:
    """Execute an ordered list of :class:`AgentStage` objects.

    Stages are run sequentially.  Each stage may be *skipped*, may
    *fail* (logged and swallowed), or may *finalize early* via an
    approval gate.

    Register stages with :meth:`register`, then call
    :meth:`run_pipeline` to execute the full chain.

    When a *progress_callback* is provided, stage lifecycle events are
    fired so callers (e.g. Slack) can keep users informed:

    * ``pipeline_stage_start``  — ``{"stage": name, "description": desc}``
    * ``pipeline_stage_complete`` — ``{"stage": name, "iterations": n}``
    * ``pipeline_stage_skipped`` — ``{"stage": name}``

    Example::

        orchestrator = AgentOrchestrator(progress_callback=my_cb)
        orchestrator.register(idea_stage)
        orchestrator.register(requirements_stage)
        orchestrator.run_pipeline()
    """

    def __init__(
        self,
        progress_callback: "Callable[[str, dict], None] | None" = None,
    ) -> None:
        self._stages: list[AgentStage] = []
        self._completed: list[str] = []
        self._skipped: list[str] = []
        self._failed: list[str] = []
        self._progress_callback = progress_callback

    # ── Registration ──────────────────────────────────────────────

    def register(self, stage: AgentStage) -> "AgentOrchestrator":
        """Append *stage* to the pipeline.  Returns ``self`` for chaining."""
        self._stages.append(stage)
        return self

    # ── Read-only accessors ───────────────────────────────────────

    @property
    def stages(self) -> list[AgentStage]:
        """All registered stages (defensive copy)."""
        return list(self._stages)

    @property
    def completed(self) -> list[str]:
        """Names of stages that ran successfully."""
        return list(self._completed)

    @property
    def skipped(self) -> list[str]:
        """Names of stages that were skipped."""
        return list(self._skipped)

    @property
    def failed(self) -> list[str]:
        """Names of stages that threw during execution."""
        return list(self._failed)

    # ── Pipeline execution ────────────────────────────────────────

    def run_pipeline(self) -> None:
        """Run every registered stage in order.

        Raises whatever ``stage.finalized_exc`` specifies when the
        user finalizes early at an approval gate.
        """
        logger.info(
            "[Orchestrator] Starting pipeline with %d stage(s): %s",
            len(self._stages),
            ", ".join(s.name for s in self._stages),
        )
        total_stages = len(self._stages)
        for idx, stage in enumerate(self._stages, 1):
            self._execute_stage(stage, step=idx, total_steps=total_stages)
        logger.info(
            "[Orchestrator] Pipeline complete — "
            "completed=%s  skipped=%s  failed=%s",
            self._completed,
            self._skipped,
            self._failed,
        )

    # ── Internal ──────────────────────────────────────────────────

    def _fire_progress(self, event_type: str, details: dict) -> None:
        """Fire the progress callback if set, swallowing errors."""
        if self._progress_callback is not None:
            try:
                self._progress_callback(event_type, details)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "progress_callback failed for %s", event_type,
                    exc_info=True,
                )

    def _execute_stage(self, stage: AgentStage, *, step: int = 0, total_steps: int = 0) -> None:
        """Run a single stage: skip → execute → apply → approve.

        The approval gate fires for both *completed* and *skipped*
        stages (a stage that was already done in a prior/resumed run
        is skipped but its approval gate must still trigger).  The gate
        is suppressed only when the stage *fails*.
        """

        # 1. Skip or execute
        if stage.should_skip():
            logger.info("[Orchestrator] Skipping '%s'", stage.name)
            self._skipped.append(stage.name)
            self._fire_progress("pipeline_stage_skipped", {
                "stage": stage.name,
                "step": step,
                "total_steps": total_steps,
            })
        else:
            # 2. Execute
            logger.info(
                "[Orchestrator] Running '%s' — %s",
                stage.name,
                stage.description,
            )
            self._fire_progress("pipeline_stage_start", {
                "stage": stage.name,
                "description": stage.description,
                "step": step,
                "total_steps": total_steps,
            })
            try:
                result = stage.run()
            except Exception:
                logger.warning(
                    "[Orchestrator] Stage '%s' failed — continuing pipeline",
                    stage.name,
                    exc_info=True,
                )
                self._failed.append(stage.name)
                return  # no approval gate on failure

            # 3. Apply result to flow state
            stage.apply(result)
            self._completed.append(stage.name)
            logger.info("[Orchestrator] Stage '%s' completed", stage.name)
            self._fire_progress("pipeline_stage_complete", {
                "stage": stage.name,
                "iterations": len(result.history) if result.history else 0,
                "step": step,
                "total_steps": total_steps,
            })

        # 4. Approval gate — fires for completed AND skipped stages
        #    (skipped = already done from a prior/resumed run)
        self._check_approval_gate(stage)

    def _check_approval_gate(self, stage: AgentStage) -> None:
        """Evaluate the stage's approval gate and raise if user finalizes."""
        if (
            stage.get_approval is not None
            and stage.requires_approval is not None
            and stage.requires_approval()
        ):
            should_finalize = stage.get_approval()
            if should_finalize and stage.finalized_exc is not None:
                logger.info(
                    "[Orchestrator] User finalized at stage '%s'",
                    stage.name,
                )
                raise stage.finalized_exc()
