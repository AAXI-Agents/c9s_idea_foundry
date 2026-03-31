"""Tests for orchestrator._startup_delivery — pending delivery discovery & crew."""

from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.orchestrator._startup_delivery import (
    _discover_pending_deliveries,
    build_startup_delivery_crew,
)

_MOD = "crewai_productfeature_planner.orchestrator._startup_delivery"
_AGENTS = "crewai_productfeature_planner.agents.orchestrator.agent"
_GET_DB = "crewai_productfeature_planner.mongodb.get_db"
_ASSEMBLE = "crewai_productfeature_planner.components.document.assemble_prd_from_doc"
_GET_REC = "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record"
_UPSERT_REC = "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record"


def _mock_db_with_docs(docs):
    """Helper: return a MagicMock get_db whose workingIdeas.find -> *docs*."""
    cursor = MagicMock()
    cursor.sort.return_value = docs
    col = MagicMock()
    col.find.return_value = cursor
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    return db


# ── _discover_pending_deliveries ─────────────────────────────────────


class TestDiscoverPendingDeliveries:
    """Tests for _discover_pending_deliveries."""

    @patch(_ASSEMBLE, return_value="")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_returns_empty_when_no_completed(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([])
        assert _discover_pending_deliveries() == []

    @patch(f"{_MOD}._has_jira_credentials", return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_returns_item_for_pending_delivery(self, mock_db, _rec, _asm, _jira):
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Dark mode",
                "executive_summary": [
                    {"content": "ES content", "iteration": 1},
                ],
            },
        ])

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert items[0]["run_id"] == "r1"
        assert items[0]["idea"] == "Dark mode"
        assert items[0]["content"] == "# PRD content"
        assert items[0]["confluence_done"] is False
        assert items[0]["jira_done"] is False
        assert items[0]["finalized_idea"] == "ES content"

    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_skips_already_completed_record(self, mock_db, mock_rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {"run_id": "r1", "status": "completed", "idea": "Done"},
        ])
        mock_rec.return_value = {"status": "completed", "jira_completed": True}

        assert _discover_pending_deliveries() == []

    @patch(f"{_MOD}._has_jira_credentials", return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_reevaluates_completed_record_when_jira_missing(
        self, mock_db, mock_rec, _asm, _jira,
    ):
        """A record marked 'completed' with jira_completed=False should
        be re-evaluated when Jira credentials are now available."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Needs Jira",
                "confluence_url": "https://wiki.test.com/p/1",
                "executive_summary": [{"content": "Summary", "iteration": 1}],
            },
        ])
        # Record says "completed" but jira_completed is False (old bug)
        mock_rec.return_value = {
            "status": "completed",
            "confluence_published": True,
            "jira_completed": False,
        }

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert items[0]["run_id"] == "r1"
        assert items[0]["confluence_done"] is True
        assert items[0]["jira_done"] is False
        assert items[0]["jira_tickets"] == []

    @patch(f"{_MOD}._has_jira_credentials", return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_includes_jira_tickets_from_record(
        self, mock_db, mock_rec, _asm, _jira,
    ):
        """Existing jira_tickets from a partial delivery record should
        be included in the DeliveryItem."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Partial Jira",
                "confluence_url": "https://wiki.test.com/p/1",
                "executive_summary": [{"content": "Summary", "iteration": 1}],
            },
        ])
        mock_rec.return_value = {
            "status": "completed",
            "confluence_published": True,
            "jira_completed": False,
            "jira_tickets": [{"key": "PRD-42", "type": "Epic"}],
        }

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert items[0]["jira_tickets"] == [{"key": "PRD-42", "type": "Epic"}]

    @patch(f"{_MOD}._has_jira_credentials", return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_item_confluence_url_from_delivery_record(
        self, mock_db, mock_rec, _asm, _jira,
    ):
        """When workingIdeas has no confluence_url but the delivery record
        does, the item dict must inherit the URL from the record."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "URL in record only",
                "executive_summary": [{"content": "Summary", "iteration": 1}],
            },
        ])
        mock_rec.return_value = {
            "status": "inprogress",
            "confluence_published": False,
            "confluence_url": "https://wiki.test.com/p/99",
            "jira_completed": False,
        }

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert items[0]["confluence_url"] == "https://wiki.test.com/p/99"

    @patch(_UPSERT_REC, return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_marks_both_done_and_skips(self, mock_db, mock_rec, _asm, mock_upsert):
        """When delivery record has confluence_published=True and jira_completed=True -> mark complete."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Both done",
            },
        ])
        mock_rec.return_value = {
            "status": "inprogress",
            "confluence_published": True,
            "confluence_url": "https://wiki.test.com/p/1",
            "jira_completed": True,
        }

        items = _discover_pending_deliveries()
        assert items == []
        mock_upsert.assert_called_once_with(
            "r1",
            confluence_published=True,
            confluence_url="https://wiki.test.com/p/1",
            jira_completed=True,
        )

    @patch(f"{_MOD}._has_jira_credentials", return_value=False)
    @patch(_UPSERT_REC, return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_no_jira_creds_does_not_mark_jira_completed(
        self, mock_db, mock_rec, _asm, mock_upsert, _jira,
    ):
        """When Jira creds are absent, jira_completed must stay False."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "No Jira creds",
            },
        ])
        mock_rec.return_value = {
            "status": "inprogress",
            "confluence_published": True,
            "confluence_url": "https://wiki.test.com/p/1",
            "jira_completed": False,
        }
        # _has_jira_credentials() returns False (no env vars in tests)
        items = _discover_pending_deliveries()
        assert items == []
        mock_upsert.assert_called_once_with(
            "r1",
            confluence_published=True,
            confluence_url="https://wiki.test.com/p/1",
            jira_completed=False,
        )

    @patch(f"{_MOD}._has_jira_credentials", return_value=False)
    @patch(_UPSERT_REC, return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_fully_done_reads_confluence_url_from_delivery_record(
        self, mock_db, mock_rec, _asm, mock_upsert, _jira,
    ):
        """Regression: When workingIdeas has no confluence_url but the
        delivery record does, the URL must be sourced from the record.

        After save_confluence_url was removed, the workingIdeas doc no
        longer stores the URL — only the productRequirements record.
        """
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "URL only in delivery record",
                # Note: NO confluence_url on workingIdeas doc
            },
        ])
        mock_rec.return_value = {
            "status": "inprogress",
            "confluence_published": True,
            "confluence_url": "https://wiki.test.com/p/1",
            "jira_completed": False,
        }

        items = _discover_pending_deliveries()
        assert items == []
        mock_upsert.assert_called_once_with(
            "r1",
            confluence_published=True,
            confluence_url="https://wiki.test.com/p/1",
            jira_completed=False,
        )

    @patch(_ASSEMBLE, return_value="")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_skips_empty_content(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {"run_id": "r1", "status": "completed", "idea": "Empty"},
        ])
        assert _discover_pending_deliveries() == []

    @patch(_GET_DB, side_effect=Exception("mongo down"))
    def test_returns_empty_on_db_failure(self, _db):
        assert _discover_pending_deliveries() == []

    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_extracts_functional_requirements(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "With FR",
                "section": {
                    "functional_requirements": [
                        {"content": "FR1: Login", "iteration": 1},
                        {"content": "FR1: Login\nFR2: Settings", "iteration": 2},
                    ],
                },
            },
        ])

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert "FR2: Settings" in items[0]["func_reqs"]

    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_skips_docs_without_run_id(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {"status": "completed", "idea": "No run id"},
        ])
        assert _discover_pending_deliveries() == []

    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_skips_item_with_interactive_jira_phase(self, mock_db, _rec, _asm):
        """Items with a non-empty jira_phase (interactive flow) should be
        skipped — the scheduler must not create tickets autonomously."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Interactive Jira",
                "jira_phase": "skeleton_pending",
            },
        ])
        items = _discover_pending_deliveries()
        assert items == []

    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_skips_epics_stories_done_phase(self, mock_db, _rec, _asm):
        """Items awaiting user review (epics_stories_done) should be skipped."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Awaiting review",
                "jira_phase": "epics_stories_done",
            },
        ])
        items = _discover_pending_deliveries()
        assert items == []

    @patch(_UPSERT_REC)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_stale_subtasks_done_not_marked_completed(
        self, mock_db, _rec, _asm, mock_upsert,
    ):
        """Regression: jira_phase='subtasks_done' with no delivery record
        is stale — must NOT blindly set jira_completed=True.

        This prevents :white_check_mark: Jira Ticketing from resurfacing
        when one-time data fixes clean the delivery record but miss the
        workingIdeas jira_phase field.
        """
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Stale Jira phase",
                "jira_phase": "subtasks_done",
            },
        ])
        items = _discover_pending_deliveries()
        assert items == []
        mock_upsert.assert_not_called()

    @patch(_UPSERT_REC)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value={
        "run_id": "r1",
        "jira_completed": True,
        "jira_tickets": [{"key": "PROJ-1"}],
    })
    @patch(_GET_DB)
    def test_marks_jira_completed_when_subtasks_done_with_evidence(
        self, mock_db, _rec, _asm, mock_upsert,
    ):
        """Items with jira_phase='subtasks_done' AND delivery record
        confirming jira_completed should be marked done.

        Only ``jira_completed`` is set — confluence fields are NOT
        passed so the delivery record's existing confluence state is
        preserved.
        """
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Jira done",
                "jira_phase": "subtasks_done",
            },
        ])
        items = _discover_pending_deliveries()
        assert items == []
        mock_upsert.assert_called_once_with(
            "r1",
            jira_completed=True,
        )

    @patch(_UPSERT_REC)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value={
        "run_id": "r1",
        "confluence_published": True,
        "confluence_url": "https://wiki.test.com/p/1",
        "jira_completed": True,
        "jira_tickets": [{"key": "PROJ-1"}],
    })
    @patch(_GET_DB)
    def test_subtasks_done_preserves_confluence_state(
        self, mock_db, _rec, _asm, mock_upsert,
    ):
        """Regression: When jira_phase='subtasks_done' and the delivery
        record has confluence_published=True, the scan must NOT reset it.

        Previously the scan read confluence_url from the workingIdeas
        doc (which is empty after the save_confluence_url migration),
        overwriting the delivery record with confluence_published=False.
        """
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Published then Jira done",
                "jira_phase": "subtasks_done",
                # Note: NO confluence_url on workingIdeas doc
            },
        ])
        items = _discover_pending_deliveries()
        assert items == []
        # Only jira_completed should be set — no confluence fields.
        mock_upsert.assert_called_once_with(
            "r1",
            jira_completed=True,
        )

    @patch(f"{_MOD}._has_jira_credentials", return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_allows_item_without_jira_phase(self, mock_db, _rec, _asm, _jira):
        """Items without jira_phase (no interactive flow started Jira)
        should proceed normally for autonomous delivery."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "No interactive Jira",
                "executive_summary": [{"content": "ES", "iteration": 1}],
            },
        ])
        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert items[0]["run_id"] == "r1"


# ── build_startup_delivery_crew ──────────────────────────────────────


class TestBuildStartupDeliveryCrew:
    """Tests for build_startup_delivery_crew."""

    _DM = f"{_AGENTS}.create_delivery_manager_agent"
    _OA = f"{_AGENTS}.create_orchestrator_agent"
    _PM = f"{_AGENTS}.create_jira_product_manager_agent"
    _ATL = f"{_AGENTS}.create_jira_architect_tech_lead_agent"
    _TC = f"{_AGENTS}.get_task_configs"
    _VERBOSE = "crewai_productfeature_planner.scripts.logging_config.is_verbose"
    _HAS_JIRA = f"{_MOD}._has_jira_credentials"
    _CREW_CLS = "crewai.Crew"
    _TASK_CLS = "crewai.Task"

    _TASK_CONFIGS = {
        "publish_to_confluence_task": {
            "description": "Publish {prd_content} as '{page_title}' ({run_id})",
            "expected_output": "Confluence page URL",
        },
        "create_jira_epic_task": {
            "description": "Create epic '{page_title}' summary={executive_summary} ({run_id}) confluence={confluence_url}",
            "expected_output": "Epic key",
        },
        "create_jira_stories_task": {
            "description": "Create stories from {approved_skeleton} {functional_requirements} {additional_prd_context} under {epic_key} ({run_id}) confluence={confluence_url}",
            "expected_output": "Story keys",
        },
        "create_jira_tasks_task": {
            "description": "Create tasks from {stories_output} reqs={functional_requirements} {additional_prd_context} ({run_id}) confluence={confluence_url}",
            "expected_output": "Task keys",
        },
    }

    def _make_item(self, **overrides):
        base = {
            "run_id": "r1",
            "idea": "Test idea",
            "content": "# PRD content",
            "confluence_done": False,
            "confluence_url": "",
            "jira_done": False,
            "jira_tickets": [],
            "finalized_idea": "ES summary",
            "func_reqs": "FR1: Login",
            "doc": {"run_id": "r1"},
        }
        base.update(overrides)
        return base

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_creates_crew_with_all_tasks(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """Should create 4 tasks when Confluence is done and Jira is pending."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(confluence_done=True))

        assert mock_task.call_count == 4  # assess + epic + stories + tasks
        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["agents"]) == 4
        assert len(crew_kwargs["tasks"]) == 4

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_defers_jira_when_confluence_pending(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should only create 2 tasks (assess + confluence) when Confluence not done yet."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(confluence_done=False))

        assert mock_task.call_count == 2  # assess + confluence only
        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["tasks"]) == 2

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_jira_when_already_done(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should create 2 tasks when Jira is done but Confluence pending."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(jira_done=True))

        assert mock_task.call_count == 2  # assess + confluence

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_stories_when_no_func_reqs_and_no_content(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """Should create 2 tasks when confluence done but no func_reqs AND no content."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(
            self._make_item(confluence_done=True, func_reqs="", content=""),
        )

        assert mock_task.call_count == 2  # assess + epic (no stories)

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_progress_callback_invoked(
        self, mock_task, mock_crew_cls, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """step_callback should invoke the progress_callback."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        cb = MagicMock()
        build_startup_delivery_crew(
            self._make_item(confluence_done=True), progress_callback=cb,
        )

        # Extract the step_callback passed to Crew
        crew_kwargs = mock_crew_cls.call_args[1]
        step_callback = crew_kwargs["step_callback"]

        # Simulate step_callback invocation
        step_output = MagicMock()
        step_output.raw = "Published page_id=123"
        step_callback(step_output)

        cb.assert_called_once()
        assert "[1/4]" in cb.call_args[0][0]

    @patch(_VERBOSE, return_value=True)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_respects_verbose_setting(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Crew verbose flag should match is_verbose()."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item())

        crew_kwargs = mock_crew.call_args[1]
        assert crew_kwargs["verbose"] is True

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_creates_jira_even_without_finalized_idea(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """Should still create Jira tasks using idea title when finalized_idea is empty."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(
            self._make_item(confluence_done=True, finalized_idea=""),
        )

        # assess + epic + stories + tasks = 4
        assert mock_task.call_count == 4
        # Epic description should use the idea title as fallback
        epic_desc = mock_task.call_args_list[1][1]["description"]
        assert "Test idea" in epic_desc

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_func_reqs_falls_back_to_content(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """When func_reqs is empty, PRD content should be used for stories."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")

        created_tasks: list[dict] = []
        def _track(**kw):
            t = MagicMock(**kw)
            created_tasks.append(kw)
            return t
        mock_task.side_effect = _track

        build_startup_delivery_crew(
            self._make_item(
                confluence_done=True,
                func_reqs="",
                content="# PRD\nFR1: User login",
            ),
        )

        # assess + epic + stories + tasks = 4
        assert len(created_tasks) == 4
        stories_desc = created_tasks[2]["description"]
        assert "# PRD" in stories_desc or "FR1: User login" in stories_desc

    @patch(_HAS_JIRA, return_value=False)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_jira_when_no_jira_credentials(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v, _hj,
    ):
        """Should skip Jira tasks when JIRA_PROJECT_KEY / creds are missing."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(
            self._make_item(confluence_done=True),
        )

        assert mock_task.call_count == 1  # assess only — Jira gated out

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_jira_tasks_use_specialized_agents(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """Epic/Stories should use PM agent; Tasks should use Architect/TL agent."""
        pm_agent = MagicMock(name="pm")
        atl_agent = MagicMock(name="atl")
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = pm_agent
        mock_atl.return_value = atl_agent

        created_tasks = []
        def _track_task(**kw):
            t = MagicMock(**kw)
            created_tasks.append(kw)
            return t
        mock_task.side_effect = _track_task

        build_startup_delivery_crew(self._make_item(confluence_done=True))

        # Tasks: assess(DM), epic(PM), stories(PM), tasks(ATL)
        assert len(created_tasks) == 4
        epic_kw = created_tasks[1]
        stories_kw = created_tasks[2]
        tasks_kw = created_tasks[3]
        assert epic_kw["agent"] is pm_agent
        assert stories_kw["agent"] is pm_agent
        assert tasks_kw["agent"] is atl_agent

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_existing_tickets_injected_into_descriptions(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v, _hj,
    ):
        """Existing Jira tickets from a partial run should appear in task descriptions."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")

        created_tasks = []
        def _track_task(**kw):
            t = MagicMock(**kw)
            created_tasks.append(kw)
            return t
        mock_task.side_effect = _track_task

        existing = [
            {"key": "PRD-42", "type": "Epic"},
            {"key": "PRD-43", "type": "Story"},
        ]
        build_startup_delivery_crew(
            self._make_item(
                confluence_done=True,
                jira_tickets=existing,
            ),
        )

        # Assess task should mention existing tickets
        assess_desc = created_tasks[0]["description"]
        assert "PRD-42" in assess_desc
        assert "PRD-43" in assess_desc

        # Epic task should mention existing Epic
        epic_desc = created_tasks[1]["description"]
        assert "PRD-42" in epic_desc

        # Stories task should mention existing stories and use Epic key
        stories_desc = created_tasks[2]["description"]
        assert "PRD-43" in stories_desc
        assert "PRD-42" in stories_desc  # epic key injected into stories format
