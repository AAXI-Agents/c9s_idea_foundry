"""Check and optionally fix Jira phase data in MongoDB.

Usage:
    .venv/bin/python scripts/check_jira_data.py          # read-only check
    .venv/bin/python scripts/check_jira_data.py --fix     # reset bogus completions
"""
import sys

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.mongodb.product_requirements import get_delivery_record

FIX = "--fix" in sys.argv

db = get_db()
docs = list(
    db["workingIdeas"]
    .find({"status": "completed"}, {"run_id": 1, "jira_phase": 1, "confluence_url": 1, "idea": 1})
)

print("=== workingIdeas (completed) ===")
for d in docs:
    run_id = d.get("run_id", "?")
    phase = d.get("jira_phase")
    conf = bool(d.get("confluence_url"))
    idea = (d.get("idea") or "")[:60]
    print(f"  run_id={run_id[:12]}  jira_phase={phase!r}  conf_url={conf}  idea={idea}")

print("\n=== delivery records ===")
fixes_needed: list[str] = []
for d in docs:
    run_id = d.get("run_id", "")
    rec = get_delivery_record(run_id)
    if rec:
        tickets = rec.get("jira_tickets") or []
        jira_done = rec.get("jira_completed")
        phase = d.get("jira_phase")
        print(
            f"  run_id={run_id[:12]}  "
            f"conf_pub={rec.get('confluence_published')}  "
            f"jira_done={jira_done}  "
            f"jira_tickets={len(tickets)}"
        )
        # Detect bogus completion: jira_completed=True but no tickets
        # and jira_phase is not "subtasks_done"
        if jira_done and not tickets and phase != "subtasks_done":
            print(f"    ⚠  BOGUS: jira_completed=True but no tickets and phase={phase!r}")
            fixes_needed.append(run_id)
    else:
        print(f"  run_id={run_id[:12]}  NO delivery record")

if fixes_needed:
    if FIX:
        print(f"\n=== Fixing {len(fixes_needed)} bogus completion(s) ===")
        from crewai_productfeature_planner.mongodb.product_requirements import upsert_delivery_record
        for run_id in fixes_needed:
            upsert_delivery_record(run_id, jira_completed=False)
            print(f"  ✓ Reset jira_completed=False for {run_id[:12]}")
        print("Done. Re-run without --fix to verify.")
    else:
        print(f"\n⚠  Found {len(fixes_needed)} bogus completion(s). Run with --fix to reset.")
else:
    print("\n✓ No issues found.")
