"""Project selection, creation, and memory configuration for the CLI.

Contains the interactive prompts for choosing or creating a project,
configuring project memory (guardrails, knowledge, tools), and linking
runs to projects.
"""
from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

__all__ = [
    "_select_or_create_project",
    "_create_project_interactive",
    "_configure_project_memory_cli",
    "_offer_memory_configuration",
    "_save_project_link",
]


def _select_or_create_project() -> tuple[str, str]:
    """Prompt the user to select an existing project or create a new one.

    This is the **first step** of the CLI PRD flow.  Every run must be
    associated with a project so that publishing (Confluence, Jira) can
    resolve project-level keys.

    Returns:
        A ``(project_id, project_name)`` tuple.
    """
    from crewai_productfeature_planner.mongodb.project_config import (
        create_project,
        list_projects,
    )

    projects = list_projects(limit=20)

    print(f"\n{'=' * 60}")
    print("  Select a Project")
    print(f"{'=' * 60}")
    if projects:
        for i, proj in enumerate(projects, 1):
            pname = proj.get("name", "Unnamed")
            space = proj.get("confluence_space_key", "")
            jira = proj.get("jira_project_key", "")
            extras = []
            if space:
                extras.append(f"confluence={space}")
            if jira:
                extras.append(f"jira={jira}")
            suffix = f"  ({', '.join(extras)})" if extras else ""
            print(f"  [{i}] {pname}{suffix}")
    else:
        print("  (no existing projects)")
    print(f"  [n] Create a new project")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose a project number, or 'n' for new: ").strip().lower()
        if choice in ("n", "new"):
            return _create_project_interactive()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                proj = projects[idx]
                pid = proj["project_id"]
                pname = proj.get("name", "Unnamed")
                print(f"\n  ✦ Selected project: {pname}")
                return pid, pname
        except ValueError:
            pass
        max_n = len(projects) if projects else 0
        print(f"Please enter 1-{max_n} or 'n'." if max_n else "Please enter 'n' to create a project.")


def _create_project_interactive() -> tuple[str, str]:
    """Walk the user through creating a new project configuration.

    Returns:
        A ``(project_id, project_name)`` tuple.
    """
    from crewai_productfeature_planner.mongodb.project_config import create_project

    print(f"\n{'=' * 60}")
    print("  Create a New Project")
    print(f"{'=' * 60}\n")

    while True:
        name = input("  Project name: ").strip()
        if name:
            break
        print("  Project name cannot be empty.")

    confluence_space_key = input(
        "  Confluence space key (press Enter to skip): "
    ).strip()
    jira_project_key = input(
        "  Jira project key (press Enter to skip): "
    ).strip()

    project_id = create_project(
        name=name,
        confluence_space_key=confluence_space_key,
        jira_project_key=jira_project_key,
    )

    if not project_id:
        print("  ⚠ Failed to create project in MongoDB — using offline mode.")
        # Generate a local project_id so the flow can still proceed
        import uuid
        project_id = uuid.uuid4().hex

    print(f"\n  ✦ Created project: {name} (id={project_id[:12]}…)")
    return project_id, name


def _configure_project_memory_cli(project_id: str, project_name: str) -> None:
    """Interactive CLI loop for configuring project memory.

    Offers the user the chance to add idea-iteration guardrails,
    knowledge references, and tool entries to the project's memory
    before starting idea iteration.  Each non-empty line entered
    becomes a separate memory entry.
    """
    from crewai_productfeature_planner.mongodb.project_memory import (
        MemoryCategory,
        add_memory_entry,
        get_project_memory,
        upsert_project_memory,
    )

    upsert_project_memory(project_id)

    _CATEGORIES = [
        (
            MemoryCategory.IDEA_ITERATION,
            "Idea & Iteration Guardrails",
            (
                "How should agents behave when iterating?\n"
                "  Examples: 'Focus on MVP features only', 'Keep iterations concise'"
            ),
        ),
        (
            MemoryCategory.KNOWLEDGE,
            "Knowledge Links & Documents",
            (
                "Links, document references, or notes that serve as guidelines.\n"
                "  Examples: 'https://wiki.example.com/api-guide', 'Follow brand guidelines v2'"
            ),
        ),
        (
            MemoryCategory.TOOLS,
            "Implementation Tools & Technologies",
            (
                "Tools, databases, frameworks, and algorithms the team uses.\n"
                "  Examples: 'MongoDB Atlas', 'FastAPI', 'React + TypeScript'"
            ),
        ),
    ]

    print(f"\n{'=' * 60}")
    print(f"  Project Memory — {project_name}")
    print(f"{'=' * 60}")

    # Show current memory if any
    doc = get_project_memory(project_id)
    has_existing = False
    if doc:
        for cat, label, _ in _CATEGORIES:
            entries = doc.get(cat.value, [])
            if entries:
                has_existing = True
                print(f"\n  {label} ({len(entries)}):")
                for e in entries:
                    print(f"    • {e.get('content', '')}")

    if has_existing:
        print(f"\n{'=' * 60}")
        print("  Memory already configured. Choose an option:")
        print("  [a] Add more entries")
        print("  [s] Skip — keep existing and continue")
        print(f"{'=' * 60}\n")
        while True:
            choice = input("Choose [a/s]: ").strip().lower()
            if choice in ("s", "skip"):
                return
            if choice in ("a", "add"):
                break
            print("Please enter 'a' to add or 's' to skip.")
    else:
        print("\n  No project memory configured yet.\n")

    for cat, label, help_text in _CATEGORIES:
        print(f"\n{'─' * 60}")
        print(f"  {label}")
        print(f"{'─' * 60}")
        print(f"  {help_text}")
        print("  Enter entries one per line. Press Enter on an empty line to finish.")
        print(f"{'─' * 60}")

        saved = 0
        while True:
            line = input("  > ").strip()
            if not line:
                break
            # Infer kind for knowledge entries
            kind = None
            if cat == MemoryCategory.KNOWLEDGE:
                kind = "link" if line.startswith(("http://", "https://")) else "note"

            ok = add_memory_entry(
                project_id, cat, line, added_by="cli", kind=kind,
            )
            if ok:
                saved += 1
        if saved:
            print(f"  ✓ Saved {saved} {label} {'entry' if saved == 1 else 'entries'}")
        else:
            print(f"  (skipped)")

    print(f"\n  ✦ Project memory configured for {project_name}")


def _offer_memory_configuration(project_id: str, project_name: str) -> None:
    """Prompt to configure memory or skip to idea iteration.

    Called after project selection in the CLI flow.
    """
    print(f"\n{'=' * 60}")
    print("  Do you want to configure project memory?")
    print(f"{'=' * 60}")
    print("  [y] Configure memory (idea guardrails, knowledge, tools)")
    print("  [n] Skip — start working on ideas")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose [y/n]: ").strip().lower()
        if choice in ("y", "yes"):
            _configure_project_memory_cli(project_id, project_name)
            return
        if choice in ("n", "no", "skip"):
            return
        print("Please enter 'y' to configure or 'n' to skip.")


def _save_project_link(run_id: str, project_id: str, *, idea: str = "") -> None:
    """Link a working-idea document to its project configuration.

    Silently ignores errors so the flow is never interrupted.
    """
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_project_ref,
        )
        save_project_ref(run_id, project_id, idea=idea)
    except Exception:  # noqa: BLE001
        logger.debug("save_project_ref failed for run_id=%s", run_id, exc_info=True)
