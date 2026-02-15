"""Iterative PRD generation flow using the Product Manager agent.

Implements a section-by-section PRD workflow:
  1. Initial Draft — PM creates each section individually, starting with
     Executive Summary. Approved sections provide context to later sections.
  2. Self-Critique — PM evaluates the current section against quality criteria.
  3. Refinement — PM addresses every gap found in the critique.
  4. Final Assembly — Once all sections are approved, the full PRD is assembled.

The user must approve each section before the flow moves to the next one.
Each iteration is persisted to MongoDB (``ideas.workingIdeas``).
The assembled final PRD is saved to ``ideas.finalizeIdeas``.
"""

import uuid
from typing import Callable, Union

from crewai import Crew, Process, Task
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.product_manager import (
    create_product_manager,
    get_task_configs,
)
from crewai_productfeature_planner.apis.prd.models import PRDDraft
from crewai_productfeature_planner.scripts.confluence_xhtml import md_to_confluence_xhtml
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.mongodb import save_failed, save_finalized, save_iteration
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool

logger = get_logger(__name__)

PAUSE_SENTINEL = "__PAUSE__"


class PauseRequested(Exception):
    """Raised when the user requests to pause and save the current iteration."""


class PRDState(BaseModel):
    """Tracks the evolving PRD through the section-by-section workflow."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    idea: str = ""
    draft: PRDDraft = Field(default_factory=PRDDraft.create_empty)
    current_section_key: str = ""
    critique: str = ""
    final_prd: str = ""
    iteration: int = 0
    is_ready: bool = False


class PRDFlow(Flow[PRDState]):
    """CrewAI Flow that drafts, critiques, and refines a PRD section by section.

    The flow processes sections in a fixed order, starting with Executive
    Summary. Each approved section is used as context for subsequent sections.

    Args:
        approval_callback: An optional callable
            ``(iteration, section_key, section_content, draft) -> bool | str``.
            Called after each section draft or refinement cycle.

            - Return ``True`` to approve the current section and move to the next.
            - Return ``False`` to continue with agent self-critique on the section.
            - Return a ``str`` to use as user-provided critique feedback
              (skips the agent self-critique and goes straight to refinement).
            - Return ``"__PAUSE__"`` to save the current state and stop the flow.

            When *not* set the flow auto-approves after the agent marks
            the section as ``SECTION_READY``.
    """

    approval_callback: Callable[[int, str, str, PRDDraft], Union[bool, str]] | None = None

    # ------------------------------------------------------------------
    # Step 1 — Generate sections one by one
    # ------------------------------------------------------------------
    @start()
    def generate_sections(self) -> str:
        """Draft each section sequentially, using approved sections as context."""
        logger.info("[Step 1] Generating PRD sections for idea: '%s'",
                    self.state.idea[:80])
        pm = create_product_manager()
        task_configs = get_task_configs()

        for section in self.state.draft.sections:
            self.state.current_section_key = section.key
            context = self.state.draft.all_sections_context(exclude_key=section.key)

            logger.info("[Draft] Generating section '%s'", section.title)
            draft_task = Task(
                description=task_configs["draft_section_task"]["description"].format(
                    section_title=section.title,
                    idea=self.state.idea,
                    context_sections=context or "(No other sections yet)",
                ),
                expected_output=task_configs["draft_section_task"]["expected_output"].format(
                    section_title=section.title,
                ),
                agent=pm,
            )
            crew = Crew(
                agents=[pm],
                tasks=[draft_task],
                process=Process.sequential,
                verbose=True,
            )
            try:
                result = crew_kickoff_with_retry(crew, step_label=f"draft_{section.key}")
            except Exception as exc:
                logger.error("[Draft] Section '%s' generation failed: %s",
                             section.title, exc)
                save_failed(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=section.iteration,
                    error=str(exc),
                    step=f"draft_{section.key}",
                )
                raise

            section.content = result.raw
            section.iteration = 1
            self.state.iteration += 1

            # Persist section draft
            save_iteration(
                run_id=self.state.run_id,
                idea=self.state.idea,
                iteration=self.state.iteration,
                draft=section.content,
                step=f"draft_{section.key}",
                section_key=section.key,
                section_title=section.title,
            )

            logger.info("[Draft] Section '%s' generated (%d chars)",
                        section.title, len(section.content))

            # --- Section approval loop ---
            self._section_approval_loop(section, pm, task_configs)

        logger.info("[Steps 1-3] All sections completed, total iterations=%d",
                    self.state.iteration)
        return self.state.draft.assemble()

    def _section_approval_loop(self, section, pm, task_configs) -> None:
        """Critique/refine a single section until user approves it."""
        while not section.is_approved:
            user_feedback: str | None = None

            # --- User approval gate ---
            if self.approval_callback is not None:
                decision = self.approval_callback(
                    section.iteration,
                    section.key,
                    section.content,
                    self.state.draft,
                )
                if decision is True:
                    section.is_approved = True
                    logger.info("[Approval] Section '%s' approved at iteration %d",
                                section.title, section.iteration)
                    break
                if decision == PAUSE_SENTINEL:
                    logger.info("[Pause] User requested pause at section '%s' iteration %d",
                                section.title, section.iteration)
                    raise PauseRequested()
                if isinstance(decision, str) and decision.strip():
                    user_feedback = decision.strip()
                    logger.info(
                        "[Approval] User provided critique for section '%s' (%d chars)",
                        section.title, len(user_feedback),
                    )

            # --- Self-Critique (skipped when user provided feedback) ---
            context = self.state.draft.all_sections_context(exclude_key=section.key)

            if user_feedback is not None:
                self.state.critique = user_feedback
                save_iteration(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=self.state.iteration,
                    draft=section.content,
                    critique=self.state.critique,
                    step=f"user_critique_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )
            else:
                logger.info("[Critique] Section '%s' — iteration %d",
                            section.title, section.iteration)
                critique_task = Task(
                    description=task_configs["critique_section_task"]["description"].format(
                        section_title=section.title,
                        section_content=section.content,
                        context_sections=context or "(No other sections available)",
                    ),
                    expected_output=task_configs["critique_section_task"]["expected_output"],
                    agent=pm,
                )
                crew = Crew(
                    agents=[pm],
                    tasks=[critique_task],
                    process=Process.sequential,
                    verbose=True,
                )
                try:
                    critique_result = crew_kickoff_with_retry(
                        crew, step_label=f"critique_{section.key}",
                    )
                except Exception as exc:
                    logger.error("[Critique] Section '%s' failed at iteration %d: %s",
                                 section.title, section.iteration, exc)
                    save_failed(
                        run_id=self.state.run_id,
                        idea=self.state.idea,
                        iteration=self.state.iteration,
                        error=str(exc),
                        draft=section.content,
                        step=f"critique_{section.key}",
                    )
                    raise
                self.state.critique = critique_result.raw
                section.critique = self.state.critique

                save_iteration(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=self.state.iteration,
                    draft=section.content,
                    critique=self.state.critique,
                    step=f"critique_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )

                # Auto-approval fallback
                if "SECTION_READY" in self.state.critique.upper() and self.approval_callback is None:
                    section.is_approved = True
                    logger.info("[Critique] Section '%s' marked SECTION_READY — auto-approved",
                                section.title)
                    break

            # --- Refinement ---
            logger.info("[Refine] Section '%s' — iteration %d",
                        section.title, section.iteration)
            refine_task = Task(
                description=task_configs["refine_section_task"]["description"].format(
                    section_title=section.title,
                    section_content=section.content,
                    critique=self.state.critique,
                    context_sections=context or "(No other sections available)",
                ),
                expected_output=task_configs["refine_section_task"]["expected_output"].format(
                    section_title=section.title,
                ),
                agent=pm,
            )
            crew = Crew(
                agents=[pm],
                tasks=[refine_task],
                process=Process.sequential,
                verbose=True,
            )
            try:
                refine_result = crew_kickoff_with_retry(
                    crew, step_label=f"refine_{section.key}",
                )
            except Exception as exc:
                logger.error("[Refine] Section '%s' failed at iteration %d: %s",
                             section.title, section.iteration, exc)
                save_failed(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=self.state.iteration,
                    error=str(exc),
                    draft=section.content,
                    step=f"refine_{section.key}",
                )
                raise
            section.content = refine_result.raw
            section.iteration += 1
            self.state.iteration += 1

            save_iteration(
                run_id=self.state.run_id,
                idea=self.state.idea,
                iteration=self.state.iteration,
                draft=section.content,
                critique=self.state.critique,
                step=f"refine_{section.key}",
                section_key=section.key,
                section_title=section.title,
            )

            logger.debug("[Refine] Section '%s' refined (%d chars)",
                         section.title, len(section.content))

    # ------------------------------------------------------------------
    # Step 4 — Final Assembly & Persist
    # ------------------------------------------------------------------
    @listen(generate_sections)
    def finalize(self) -> str:
        """Assemble the final PRD from all approved sections and persist."""
        logger.info("[Step 4] Finalising PRD (total iterations=%d)", self.state.iteration)
        self.state.final_prd = self.state.draft.assemble()

        # Save Markdown to file
        writer = PRDFileWriteTool()
        save_result = writer._run(
            content=self.state.final_prd,
            filename="",
            version=self.state.iteration,
        )

        # Convert to Confluence-compatible XHTML
        confluence_xhtml = md_to_confluence_xhtml(self.state.final_prd)
        logger.info(
            "[Step 4] Generated Confluence XHTML (%d chars)", len(confluence_xhtml)
        )

        # Save to MongoDB finalizeIdeas (Markdown + XHTML)
        save_finalized(
            run_id=self.state.run_id,
            idea=self.state.idea,
            iteration=self.state.iteration,
            final_prd=self.state.final_prd,
            confluence_xhtml=confluence_xhtml,
        )

        logger.info("[Step 4] %s", save_result)
        return save_result
