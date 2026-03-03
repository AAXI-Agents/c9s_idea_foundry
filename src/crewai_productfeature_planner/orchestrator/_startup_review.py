"""Startup Markdown Review stage and pipeline.

Scans for unpublished PRDs (from MongoDB and disk) and publishes them
to Confluence on server/CLI startup.
"""

from __future__ import annotations

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_confluence_credentials,
    logger,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    AgentStage,
    StageResult,
)


# ── Discovery helper ─────────────────────────────────────────────────


def _discover_publishable_prds() -> list[dict]:
    """Find PRDs ready for Confluence publishing from MongoDB and disk.

    Combines two sources:

    1. **MongoDB** — completed working ideas whose ``confluence_url``
       is missing or empty.
    2. **Disk** — markdown files under ``output/prds/`` that are not
       already tracked in MongoDB (e.g. manually placed files).

    Returns:
        A list of dicts, each containing ``run_id``, ``title``,
        ``content``, ``source`` (``"mongodb"`` or ``"disk"``), and
        ``output_file``.
    """
    items: list[dict] = []
    seen_files: set[str] = set()

    # ── Source 1: MongoDB ──────────────────────────────────────
    try:
        from crewai_productfeature_planner.components.document import assemble_prd_from_doc
        from crewai_productfeature_planner.mongodb import (
            find_completed_without_confluence,
        )

        docs = find_completed_without_confluence()
        for doc in docs:
            run_id = doc.get("run_id", "")
            if not run_id:
                continue
            content = assemble_prd_from_doc(doc)
            if not content:
                continue
            idea = (doc.get("idea") or "PRD")[:80].strip()
            output_file = doc.get("output_file", "")
            if output_file:
                seen_files.add(output_file)
            items.append({
                "run_id": run_id,
                "title": f"PRD — {idea}",
                "content": content,
                "source": "mongodb",
                "output_file": output_file,
            })
    except Exception as exc:
        logger.warning(
            "[StartupMarkdownReview] Failed to query MongoDB: %s", exc,
        )

    # ── Source 2: Disk — output/prds/ ──────────────────────────
    try:
        from pathlib import Path

        prds_dir = Path(__file__).resolve().parents[2] / "output" / "prds"
        drafts_dir = prds_dir / "_drafts"
        if prds_dir.exists():
            for md_file in sorted(prds_dir.rglob("*.md")):
                abs_path = str(md_file)

                # Skip files inside the _drafts/ directory — those are
                # partial/paused progress saves, not completed PRDs.
                try:
                    if md_file.resolve().is_relative_to(drafts_dir.resolve()):
                        continue
                except (ValueError, TypeError):
                    pass

                # Skip files already covered by the MongoDB source
                if any(abs_path.endswith(sf) for sf in seen_files):
                    continue

                content = md_file.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                # Skip in-progress documents that were saved before
                # the _drafts/ directory convention was introduced.
                if content.lstrip().startswith(
                    "# Product Requirements Document (In Progress)"
                ):
                    continue

                items.append({
                    "run_id": "",
                    "title": f"PRD — {md_file.stem}",
                    "content": content,
                    "source": "disk",
                    "output_file": abs_path,
                })
    except Exception as exc:
        logger.warning(
            "[StartupMarkdownReview] Failed to scan output/prds/: %s",
            exc,
        )

    return items


# ── Stage factory ─────────────────────────────────────────────────────


def build_startup_markdown_review_stage() -> AgentStage:
    """Create an :class:`AgentStage` that reviews and publishes
    unpublished PRD markdown files to Confluence.

    **Stage 1** of the startup pipeline.  Operates independently of
    any :class:`PRDFlow` — it scans all completed runs and disk files.

    Workflow:

    1. Verify Confluence credentials are configured.
    2. Discover publishable PRDs from MongoDB and ``output/prds/``.
    3. Publish each to Confluence (create or update).
    4. Record the ``confluence_url`` back in MongoDB.
    """
    # Shared mutable state between should_skip → run
    _ctx: dict = {"items": []}

    def _should_skip() -> bool:
        if not _has_confluence_credentials():
            logger.info(
                "[StartupMarkdownReview] Skipping — Confluence "
                "credentials not configured"
            )
            return True
        items = _discover_publishable_prds()
        if not items:
            logger.info(
                "[StartupMarkdownReview] Skipping — no unpublished "
                "PRDs found"
            )
            return True
        _ctx["items"] = items
        logger.info(
            "[StartupMarkdownReview] Found %d unpublished PRD(s) to "
            "review",
            len(items),
        )
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.tools.confluence_tool import (
            publish_to_confluence,
        )

        items = _ctx["items"]
        published_urls: list[str] = []
        errors: list[str] = []

        for item in items:
            try:
                result = publish_to_confluence(
                    title=item["title"],
                    markdown_content=item["content"],
                    run_id=item.get("run_id", ""),
                )
                url = result.get("url", "")
                page_id = result.get("page_id", "")

                if not url:
                    errors.append(f"{item['title']}: no URL returned")
                    logger.warning(
                        "[StartupMarkdownReview] Publish returned no URL "
                        "for '%s'",
                        item["title"],
                    )
                    continue

                published_urls.append(f"{item['title']}: {url}")

                # Persist confluence_url in MongoDB when run_id is known
                if item.get("run_id"):
                    from crewai_productfeature_planner.mongodb import (
                        save_confluence_url,
                    )

                    save_confluence_url(
                        run_id=item["run_id"],
                        confluence_url=url,
                        page_id=page_id,
                    )

                logger.info(
                    "[StartupMarkdownReview] Published '%s' → %s",
                    item["title"],
                    url,
                )
            except Exception as exc:
                errors.append(f"{item['title']}: {exc}")
                logger.warning(
                    "[StartupMarkdownReview] Failed to publish '%s': %s",
                    item["title"],
                    exc,
                )

        output = (
            f"Published {len(published_urls)} PRD(s) to Confluence.\n"
            + "\n".join(published_urls)
        )

        # When every publish failed, raise so the stage is marked failed
        if not published_urls and errors:
            raise RuntimeError(
                f"All {len(errors)} Confluence publish(es) failed: "
                + "; ".join(errors)
            )

        return StageResult(output=output)

    def _apply(result: StageResult) -> None:
        # Output is informational — side-effects are handled in _run.
        logger.info(
            "[StartupMarkdownReview] Stage completed: %s",
            result.output.split("\n", 1)[0],
        )

    return AgentStage(
        name="startup_markdown_review",
        description=(
            "Review available markdown PRDs and publish to Confluence"
        ),
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# ── Pipeline assembly ─────────────────────────────────────────────────


def build_startup_pipeline() -> AgentOrchestrator:
    """Assemble the startup review pipeline.

    Runs on server or CLI startup to catch up on any pending Confluence
    publishing from previous sessions.

    Current chain::

        1. Markdown Review — scan for unpublished PRDs and publish
           to Confluence

    Returns:
        A fully-configured :class:`AgentOrchestrator` ready for
        :meth:`~AgentOrchestrator.run_pipeline`.
    """
    orchestrator = AgentOrchestrator()
    orchestrator.register(build_startup_markdown_review_stage())
    return orchestrator
