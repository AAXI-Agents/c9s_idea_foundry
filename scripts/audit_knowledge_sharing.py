#!/usr/bin/env python3
"""Audit + delete all MongoDB documents for 'knowledge sharing' idea."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

from crewai_productfeature_planner.mongodb.client import get_db

db = get_db()

DELETE = "--delete" in sys.argv

pattern = re.compile("knowledge sharing", re.IGNORECASE)

# ── workingIdeas ──────────────────────────────────────────────
wi_query = {"$or": [
    {"idea": pattern},
    {"finalized_idea": pattern},
    {"idea_normalized": pattern},
]}
docs = list(db["workingIdeas"].find(wi_query, {
    "run_id": 1, "idea": 1, "status": 1, "created_at": 1,
    "project_id": 1, "slack_channel": 1, "idea_normalized": 1,
    "jira_phase": 1, "output_file": 1,
}))
print(f"\n=== workingIdeas matching 'knowledge sharing': {len(docs)} ===")
run_ids = []
for d in sorted(docs, key=lambda x: x.get("created_at", "")):
    rid = d.get("run_id", "?")
    run_ids.append(rid)
    print(
        f"  run_id={rid}  status={d.get('status'):<12s}  "
        f"project_id={d.get('project_id') or '(none)'}  "
        f"jira_phase={d.get('jira_phase') or '(none)'}  "
        f"created={str(d.get('created_at', ''))[:19]}  "
        f"idea_normalized={'yes' if d.get('idea_normalized') else 'NO'}"
    )

# ── productRequirements ──────────────────────────────────────
pr_docs = list(db["productRequirements"].find(
    {"run_id": {"$in": run_ids}},
    {"run_id": 1, "confluence_published": 1, "confluence_url": 1,
     "jira_completed": 1, "jira_tickets": 1, "status": 1},
))
print(f"\n=== productRequirements: {len(pr_docs)} ===")
for d in pr_docs:
    tickets = d.get("jira_tickets") or []
    print(
        f"  run_id={d.get('run_id')}  "
        f"confluence_published={d.get('confluence_published')}  "
        f"confluence_url={str(d.get('confluence_url', ''))[:60]}  "
        f"jira_completed={d.get('jira_completed')}  "
        f"jira_tickets={len(tickets)} tickets  "
        f"status={d.get('status')}"
    )

# ── crewJobs ──────────────────────────────────────────────────
cj_docs = list(db["crewJobs"].find(
    {"run_id": {"$in": run_ids}},
    {"run_id": 1, "status": 1, "flow_type": 1, "created_at": 1},
))
print(f"\n=== crewJobs: {len(cj_docs)} ===")
for d in sorted(cj_docs, key=lambda x: x.get("created_at", "")):
    print(
        f"  run_id={d.get('run_id')}  status={d.get('status')}  "
        f"flow_type={d.get('flow_type')}  "
        f"created={str(d.get('created_at', ''))[:19]}"
    )

# ── agentInteractions ─────────────────────────────────────────
ai_count = db["agentInteractions"].count_documents({"run_id": {"$in": run_ids}})
print(f"\n=== agentInteractions: {ai_count} total ===")

# ── output files on disk ──────────────────────────────────────
output_files = []
for d in docs:
    of = d.get("output_file")
    if of:
        output_files.append(of)
if output_files:
    print(f"\n=== output files: {len(output_files)} ===")
    for f in output_files:
        p = Path(f)
        exists = p.exists() if p.is_absolute() else (Path(__file__).resolve().parents[1] / f).exists()
        print(f"  {f}  exists={exists}")

# ── DELETE ────────────────────────────────────────────────────
if DELETE:
    print("\n=== DELETING ALL DOCUMENTS ===")
    r1 = db["workingIdeas"].delete_many(wi_query)
    print(f"  workingIdeas: deleted {r1.deleted_count}")
    r2 = db["productRequirements"].delete_many({"run_id": {"$in": run_ids}})
    print(f"  productRequirements: deleted {r2.deleted_count}")
    r3 = db["crewJobs"].delete_many({"run_id": {"$in": run_ids}})
    print(f"  crewJobs: deleted {r3.deleted_count}")
    r4 = db["agentInteractions"].delete_many({"run_id": {"$in": run_ids}})
    print(f"  agentInteractions: deleted {r4.deleted_count}")
    print("\nDone. All 'knowledge sharing' references removed from MongoDB.")
else:
    print(f"\n--- DRY RUN — pass --delete to remove all {len(docs)} workingIdeas + related docs ---")
