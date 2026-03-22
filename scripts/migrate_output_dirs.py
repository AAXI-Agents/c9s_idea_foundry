#!/usr/bin/env python3
"""One-time migration: reorganise output files into project-based directories.

Old layout:
    output/prds/YYYY/MM/prd_v{N}_{ts}.md
    output/prds/YYYY/MM/ux_design_{ts}.md
    output/prds/_drafts/YYYY/MM/prd_v{N}_{ts}.md

New layout:
    output/{project_id}/product requirement documents/prd_v{N}_{ts}.md
    output/{project_id}/ux design/ux_design_{ts}.md
    output/{project_id}/product requirement documents/_drafts/prd_v{N}_{ts}.md

Steps:
    1. Query all workingIdeas documents with an output_file or ux_output_file field.
    2. For each document that has a project_id:
       a. Compute the new file path based on project_id.
       b. Move the file on disk.
       c. Update the MongoDB output_file / ux_output_file field.
    3. Print before/after for all affected documents.

Usage:
    .venv/bin/python scripts/migrate_output_dirs.py [--dry-run]

After verification, delete this script per project convention.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports.
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root / "src"))

from crewai_productfeature_planner.mongodb.client import get_db  # noqa: E402
from crewai_productfeature_planner.mongodb.working_ideas._common import (  # noqa: E402
    WORKING_COLLECTION,
)


def _compute_new_path(
    old_path: str,
    project_id: str,
    file_type: str,
) -> str | None:
    """Compute the new file path under the project-based directory.

    Args:
        old_path: The current file path (relative or absolute).
        project_id: The project identifier.
        file_type: Either "prd" or "ux".

    Returns:
        The new relative path, or None if the path is already migrated.
    """
    p = Path(old_path)
    filename = p.name

    # Detect if the file is already in the new layout.
    if f"output/{project_id}/" in old_path:
        return None

    if file_type == "ux":
        new_dir = Path("output") / project_id / "ux design"
    elif "_drafts" in old_path:
        new_dir = Path("output") / project_id / "product requirement documents" / "_drafts"
    else:
        new_dir = Path("output") / project_id / "product requirement documents"

    return str(new_dir / filename)


def _move_file(old_path: str, new_path: str, *, dry_run: bool) -> bool:
    """Move a file from old_path to new_path.

    Returns True if the move succeeded (or would succeed in dry-run).
    """
    old_p = Path(old_path)
    new_p = Path(new_path)

    if not old_p.is_file():
        print(f"  SKIP (file not found): {old_path}")
        return False

    if dry_run:
        print(f"  DRY-RUN move: {old_path} -> {new_path}")
        return True

    new_p.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_p), str(new_p))
    print(f"  MOVED: {old_path} -> {new_path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate output files to project-based directory layout.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without moving files or updating MongoDB.",
    )
    args = parser.parse_args()
    dry_run: bool = args.dry_run

    if dry_run:
        print("=== DRY RUN MODE — no files will be moved, no DB changes ===\n")

    db = get_db()
    collection = db[WORKING_COLLECTION]

    # Find all documents that have output_file or ux_output_file set
    # and have a project_id.
    query = {
        "project_id": {"$exists": True, "$ne": None, "$ne": ""},
        "$or": [
            {"output_file": {"$exists": True, "$ne": None, "$ne": ""}},
            {"ux_output_file": {"$exists": True, "$ne": None, "$ne": ""}},
        ],
    }
    docs = list(collection.find(query))
    print(f"Found {len(docs)} document(s) with file references and project_id.\n")

    migrated = 0
    skipped = 0
    errors = 0

    for doc in docs:
        run_id = doc.get("run_id", "")
        project_id = doc.get("project_id", "")
        output_file = doc.get("output_file", "")
        ux_output_file = doc.get("ux_output_file", "")

        print(f"--- run_id={run_id}, project_id={project_id}")

        update_fields: dict[str, str] = {}

        # Migrate PRD output file.
        if output_file:
            new_path = _compute_new_path(output_file, project_id, "prd")
            if new_path:
                print(f"  PRD: {output_file} -> {new_path}")
                if _move_file(output_file, new_path, dry_run=dry_run):
                    update_fields["output_file"] = new_path
                    migrated += 1
                else:
                    # File not found on disk — still update the DB ref
                    # so it points to the expected new location.
                    update_fields["output_file"] = new_path
                    errors += 1
            else:
                print(f"  PRD: already migrated ({output_file})")
                skipped += 1

        # Migrate UX output file.
        if ux_output_file:
            new_path = _compute_new_path(ux_output_file, project_id, "ux")
            if new_path:
                print(f"  UX:  {ux_output_file} -> {new_path}")
                if _move_file(ux_output_file, new_path, dry_run=dry_run):
                    update_fields["ux_output_file"] = new_path
                    migrated += 1
                else:
                    update_fields["ux_output_file"] = new_path
                    errors += 1
            else:
                print(f"  UX:  already migrated ({ux_output_file})")
                skipped += 1

        # Update MongoDB.
        if update_fields and not dry_run:
            from datetime import datetime, timezone

            update_fields["update_date"] = datetime.now(timezone.utc).isoformat()
            collection.update_one(
                {"run_id": run_id},
                {"$set": update_fields},
            )
            print(f"  DB updated: {list(update_fields.keys())}")

    print(f"\n=== Summary ===")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")

    # Verify — re-query and print final state.
    print("\n=== Verification ===")
    docs_after = list(collection.find(
        {"$or": [
            {"output_file": {"$exists": True, "$ne": None, "$ne": ""}},
            {"ux_output_file": {"$exists": True, "$ne": None, "$ne": ""}},
        ]},
        {"run_id": 1, "project_id": 1, "output_file": 1, "ux_output_file": 1, "_id": 0},
    ))
    for doc in docs_after:
        print(f"  run_id={doc.get('run_id')}")
        print(f"    project_id={doc.get('project_id', '')}")
        print(f"    output_file={doc.get('output_file', '')}")
        print(f"    ux_output_file={doc.get('ux_output_file', '')}")


if __name__ == "__main__":
    main()
