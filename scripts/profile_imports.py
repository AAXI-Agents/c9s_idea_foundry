"""One-time script to profile module import times — post-fix."""
import time
import sys
import types

# Block apis/__init__.py from running by pre-registering an empty module
apis_mod = types.ModuleType("crewai_productfeature_planner.apis")
apis_mod.__path__ = [
    "src/crewai_productfeature_planner/apis",
]
apis_mod.__package__ = "crewai_productfeature_planner.apis"
sys.modules["crewai_productfeature_planner.apis"] = apis_mod

# Also block slack sub-package from auto-importing
slack_mod = types.ModuleType("crewai_productfeature_planner.apis.slack")
slack_mod.__path__ = [
    "src/crewai_productfeature_planner/apis/slack",
]
slack_mod.__package__ = "crewai_productfeature_planner.apis.slack"
sys.modules["crewai_productfeature_planner.apis.slack"] = slack_mod

# Block prd sub-package
prd_mod = types.ModuleType("crewai_productfeature_planner.apis.prd")
prd_mod.__path__ = [
    "src/crewai_productfeature_planner/apis/prd",
]
prd_mod.__package__ = "crewai_productfeature_planner.apis.prd"
sys.modules["crewai_productfeature_planner.apis.prd"] = prd_mod

start = time.time()
results = []


def measure(label, module_name):
    t0 = time.time()
    __import__(module_name)
    elapsed = time.time() - t0
    results.append((label, elapsed))
    print(f"  {label}: {elapsed:.3f}s", flush=True)


print("=== Isolated Router Import (Post-Fix) ===\n", flush=True)

measure("health.router", "crewai_productfeature_planner.apis.health.router")
measure("ideas.router", "crewai_productfeature_planner.apis.ideas.router")
measure("prd._agents", "crewai_productfeature_planner.apis.prd._agents")
measure("prd._sections", "crewai_productfeature_planner.apis.prd._sections")
measure("prd._domain", "crewai_productfeature_planner.apis.prd._domain")
measure("prd._requests", "crewai_productfeature_planner.apis.prd._requests")
measure("prd._responses", "crewai_productfeature_planner.apis.prd._responses")
measure("prd._jobs", "crewai_productfeature_planner.apis.prd._jobs")
measure("prd._errors", "crewai_productfeature_planner.apis.prd._errors")
measure("prd.models", "crewai_productfeature_planner.apis.prd.models")
measure("shared", "crewai_productfeature_planner.apis.shared")
measure("prd.service", "crewai_productfeature_planner.apis.prd.service")
measure("prd.router", "crewai_productfeature_planner.apis.prd.router")
measure("projects.router", "crewai_productfeature_planner.apis.projects.router")
measure("publishing.router", "crewai_productfeature_planner.apis.publishing.router")
measure("slack.router", "crewai_productfeature_planner.apis.slack.router")
measure("slack.events_router", "crewai_productfeature_planner.apis.slack.events_router")
measure("slack.interactions_router", "crewai_productfeature_planner.apis.slack.interactions_router")
measure("slack.oauth_router", "crewai_productfeature_planner.apis.slack.oauth_router")
measure("sso_webhooks", "crewai_productfeature_planner.apis.sso_webhooks")

total = time.time() - start
print(f"\n=== Total: {total:.3f}s ===", flush=True)
print(f"\nTop 5 slowest:", flush=True)
for label, elapsed in sorted(results, key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {label}: {elapsed:.3f}s", flush=True)
