#!/usr/bin/env python3
"""One-time migration: export all data from localhost MongoDB to MongoDB Atlas.

Creates the target database and all collections on Atlas, copies every
document, and rebuilds indexes.

Usage::

    # Dry run — shows what would be migrated without writing anything
    python scripts/migrate_to_atlas.py --dry-run

    # Full migration (default source: mongodb://localhost:27017)
    python scripts/migrate_to_atlas.py

    # Custom source URI
    python scripts/migrate_to_atlas.py --source mongodb://localhost:27017

Environment:
    MONGODB_ATLAS_URI  — target Atlas connection string (required, read from .env)
    MONGODB_DB         — database name (default: ideas)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# ---------------------------------------------------------------------------
# Resolve project .env
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_atlas_uri() -> str:
    uri = os.environ.get("MONGODB_ATLAS_URI", "").strip()
    if not uri:
        print("ERROR: MONGODB_ATLAS_URI is not set in environment or .env")
        sys.exit(1)
    return uri


def _get_db_name() -> str:
    from crewai_productfeature_planner.mongodb.client import DEFAULT_DB_NAME
    return os.environ.get("MONGODB_DB", "").strip() or DEFAULT_DB_NAME


def _safe_host(uri: str) -> str:
    """Return the host portion of a URI (after @) for safe logging."""
    return uri.split("@")[-1] if "@" in uri else uri


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate(source_uri: str, dry_run: bool = False) -> None:
    atlas_uri = _get_atlas_uri()
    db_name = _get_db_name()

    print(f"Source : {_safe_host(source_uri)}")
    print(f"Target : {_safe_host(atlas_uri)}")
    print(f"Database: {db_name}")
    print(f"Mode   : {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # ── Connect to source ────────────────────────────────────
    try:
        src_client: MongoClient = MongoClient(
            source_uri, serverSelectionTimeoutMS=5_000
        )
        src_client.admin.command("ping")
    except PyMongoError as exc:
        print(f"ERROR: Cannot connect to source MongoDB: {exc}")
        sys.exit(1)

    src_db = src_client[db_name]
    collections = src_db.list_collection_names()

    if not collections:
        print("No collections found in source database — nothing to migrate.")
        src_client.close()
        return

    print(f"Found {len(collections)} collection(s): {', '.join(sorted(collections))}")
    print()

    # ── Connect to target ────────────────────────────────────
    try:
        tgt_client: MongoClient = MongoClient(
            atlas_uri,
            serverSelectionTimeoutMS=10_000,
            tls=True,
            tlsCAFile=certifi.where(),
        )
        tgt_client.admin.command("ping")
    except PyMongoError as exc:
        print(f"ERROR: Cannot connect to Atlas: {exc}")
        src_client.close()
        sys.exit(1)

    tgt_db = tgt_client[db_name]
    existing_target = set(tgt_db.list_collection_names())

    total_docs = 0
    total_collections = 0

    for col_name in sorted(collections):
        src_col = src_db[col_name]
        doc_count = src_col.count_documents({})
        print(f"  {col_name}: {doc_count} document(s)", end="")

        if dry_run:
            print(" [dry-run, skipped]")
            total_docs += doc_count
            total_collections += 1
            continue

        # Create collection on Atlas if it doesn't exist
        if col_name not in existing_target:
            try:
                tgt_db.create_collection(col_name)
                print(f" — created collection", end="")
            except PyMongoError as exc:
                print(f" — WARN: create_collection failed: {exc}", end="")

        tgt_col = tgt_db[col_name]

        # Copy documents in batches
        if doc_count > 0:
            batch_size = 500
            inserted = 0
            cursor = src_col.find({})
            batch: list[dict] = []

            for doc in cursor:
                # Remove _id so Atlas generates new ones — unless you want
                # to preserve _id (which is the default for migrations).
                batch.append(doc)
                if len(batch) >= batch_size:
                    try:
                        tgt_col.insert_many(batch, ordered=False)
                        inserted += len(batch)
                    except PyMongoError as exc:
                        # Duplicate key errors are expected if re-running
                        if "duplicate key" in str(exc).lower():
                            dupes = getattr(exc, "details", {}).get(
                                "nInserted", 0
                            )
                            inserted += dupes
                            print(
                                f" — WARN: {len(batch) - dupes} duplicate(s) skipped",
                                end="",
                            )
                        else:
                            print(f" — ERROR: {exc}", end="")
                    batch = []

            # Flush remaining
            if batch:
                try:
                    tgt_col.insert_many(batch, ordered=False)
                    inserted += len(batch)
                except PyMongoError as exc:
                    if "duplicate key" in str(exc).lower():
                        dupes = getattr(exc, "details", {}).get("nInserted", 0)
                        inserted += dupes
                    else:
                        print(f" — ERROR: {exc}", end="")

            print(f" — {inserted} inserted", end="")

        # Copy indexes (skip the default _id index)
        src_indexes = src_col.index_information()
        idx_count = 0
        for idx_name, idx_spec in src_indexes.items():
            if idx_name == "_id_":
                continue
            try:
                kwargs: dict = {}
                if idx_spec.get("unique"):
                    kwargs["unique"] = True
                if idx_spec.get("sparse"):
                    kwargs["sparse"] = True
                tgt_col.create_index(idx_spec["key"], name=idx_name, **kwargs)
                idx_count += 1
            except PyMongoError:
                pass  # index may already exist

        if idx_count:
            print(f", {idx_count} index(es)", end="")

        print()  # newline
        total_docs += doc_count
        total_collections += 1

    print()
    print(f"Migration {'preview' if dry_run else 'complete'}:")
    print(f"  Collections: {total_collections}")
    print(f"  Documents  : {total_docs}")

    src_client.close()
    tgt_client.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate local MongoDB data to MongoDB Atlas."
    )
    parser.add_argument(
        "--source",
        default="mongodb://localhost:27017",
        help="Source MongoDB URI (default: mongodb://localhost:27017)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be migrated without writing anything.",
    )
    args = parser.parse_args()
    migrate(source_uri=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
