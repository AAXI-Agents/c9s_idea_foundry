"""Seed the agentRegistry collection with all known CrewAI agents.

Populates the org chart with departments, reporting lines, capabilities,
and default budget config. Idempotent — uses upsert so repeated runs
only update existing records.

Usage:
    .venv/bin/python -m crewai_productfeature_planner.scripts.seed_agent_registry
"""

from __future__ import annotations

from crewai_productfeature_planner.mongodb.agent_registry import upsert_agent
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Agent definitions ─────────────────────────────────────────
#
# Each entry defines an agent's org-chart position, capabilities,
# and default budget. The list is ordered by department hierarchy.

AGENTS: list[dict] = [
    # ── Product Department ────────────────────────────────────
    {
        "agent_id": "product_manager",
        "display_name": "Product Manager",
        "department": "product",
        "role": "Head of Product",
        "title": "Senior Product Manager",
        "reports_to": None,
        "avatar": "📋",
        "llm_tier": "gemini_research",
        "capabilities": [
            "prd_drafting",
            "requirements_analysis",
            "executive_summary",
            "feature_definition",
            "acceptance_criteria",
        ],
        "budget": {
            "monthly_token_limit": 2_000_000,
            "monthly_cost_limit_usd": 50.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "idea_refiner",
        "display_name": "Idea Refiner",
        "department": "product",
        "role": "Idea Development",
        "title": "Idea Refinement Specialist",
        "reports_to": "product_manager",
        "avatar": "💡",
        "llm_tier": "gemini_research",
        "capabilities": [
            "idea_clarification",
            "gap_analysis",
            "iterative_refinement",
            "scope_definition",
        ],
        "budget": {
            "monthly_token_limit": 1_500_000,
            "monthly_cost_limit_usd": 35.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "requirements_breakdown",
        "display_name": "Requirements Analyst",
        "department": "product",
        "role": "Requirements",
        "title": "Requirements Breakdown Specialist",
        "reports_to": "product_manager",
        "avatar": "📐",
        "llm_tier": "gemini_research",
        "capabilities": [
            "requirements_decomposition",
            "user_stories",
            "dependency_mapping",
            "priority_ranking",
        ],
        "budget": {
            "monthly_token_limit": 1_500_000,
            "monthly_cost_limit_usd": 35.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "ux_designer",
        "display_name": "UX Designer",
        "department": "product",
        "role": "Design",
        "title": "Senior UX Designer",
        "reports_to": "product_manager",
        "avatar": "🎨",
        "llm_tier": "gemini_research",
        "capabilities": [
            "wireframing",
            "user_flows",
            "accessibility_review",
            "design_system",
            "interaction_patterns",
        ],
        "budget": {
            "monthly_token_limit": 1_000_000,
            "monthly_cost_limit_usd": 25.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    # ── Engineering Department ────────────────────────────────
    {
        "agent_id": "eng_manager",
        "display_name": "Engineering Manager",
        "department": "engineering",
        "role": "Head of Engineering",
        "title": "Engineering Manager",
        "reports_to": None,
        "avatar": "⚙️",
        "llm_tier": "gemini_research",
        "capabilities": [
            "technical_review",
            "architecture_validation",
            "effort_estimation",
            "risk_assessment",
            "team_allocation",
        ],
        "budget": {
            "monthly_token_limit": 1_500_000,
            "monthly_cost_limit_usd": 35.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "staff_engineer",
        "display_name": "Staff Engineer",
        "department": "engineering",
        "role": "Technical Lead",
        "title": "Staff Engineer",
        "reports_to": "eng_manager",
        "avatar": "🏗️",
        "llm_tier": "gemini_research",
        "capabilities": [
            "system_design",
            "api_design",
            "scalability_review",
            "tech_debt_analysis",
            "implementation_plan",
        ],
        "budget": {
            "monthly_token_limit": 1_500_000,
            "monthly_cost_limit_usd": 35.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "qa_lead",
        "display_name": "QA Lead",
        "department": "engineering",
        "role": "Quality Assurance",
        "title": "QA Lead",
        "reports_to": "eng_manager",
        "avatar": "🔍",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "test_strategy",
            "test_plan",
            "quality_gates",
            "regression_planning",
        ],
        "budget": {
            "monthly_token_limit": 1_000_000,
            "monthly_cost_limit_usd": 20.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "qa_engineer",
        "display_name": "QA Engineer",
        "department": "engineering",
        "role": "Quality Assurance",
        "title": "QA Engineer",
        "reports_to": "qa_lead",
        "avatar": "🧪",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "test_cases",
            "edge_case_analysis",
            "acceptance_testing",
            "scenario_generation",
        ],
        "budget": {
            "monthly_token_limit": 1_000_000,
            "monthly_cost_limit_usd": 20.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    # ── Operations Department ─────────────────────────────────
    {
        "agent_id": "orchestrator",
        "display_name": "Orchestrator",
        "department": "operations",
        "role": "Head of Operations",
        "title": "Flow Orchestrator",
        "reports_to": None,
        "avatar": "🎯",
        "llm_tier": "basic",
        "capabilities": [
            "pipeline_management",
            "flow_coordination",
            "state_machine",
            "error_recovery",
            "resource_allocation",
        ],
        "budget": {
            "monthly_token_limit": 500_000,
            "monthly_cost_limit_usd": 10.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "engagement_manager",
        "display_name": "Engagement Manager",
        "department": "operations",
        "role": "Stakeholder Relations",
        "title": "Engagement Manager",
        "reports_to": "orchestrator",
        "avatar": "🤝",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "stakeholder_communication",
            "progress_reporting",
            "approval_management",
            "feedback_collection",
        ],
        "budget": {
            "monthly_token_limit": 500_000,
            "monthly_cost_limit_usd": 10.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "release_engineer",
        "display_name": "Release Engineer",
        "department": "operations",
        "role": "Delivery",
        "title": "Release Engineer",
        "reports_to": "orchestrator",
        "avatar": "🚀",
        "llm_tier": "basic",
        "capabilities": [
            "confluence_publishing",
            "jira_ticketing",
            "delivery_management",
            "artifact_packaging",
        ],
        "budget": {
            "monthly_token_limit": 500_000,
            "monthly_cost_limit_usd": 10.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "retro_manager",
        "display_name": "Retrospective Manager",
        "department": "operations",
        "role": "Process Improvement",
        "title": "Retro Manager",
        "reports_to": "orchestrator",
        "avatar": "🔄",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "retrospective_facilitation",
            "process_analysis",
            "improvement_tracking",
            "knowledge_capture",
        ],
        "budget": {
            "monthly_token_limit": 500_000,
            "monthly_cost_limit_usd": 10.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "ceo_reviewer",
        "display_name": "CEO Reviewer",
        "department": "operations",
        "role": "Executive Review",
        "title": "Chief Executive Reviewer",
        "reports_to": None,
        "avatar": "👔",
        "llm_tier": "gemini_research",
        "capabilities": [
            "strategic_review",
            "business_alignment",
            "go_no_go_decision",
            "executive_feedback",
        ],
        "budget": {
            "monthly_token_limit": 500_000,
            "monthly_cost_limit_usd": 15.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    # ── Ideation Department ───────────────────────────────────
    {
        "agent_id": "product_ideation_specialist",
        "display_name": "Product Ideation Specialist",
        "department": "ideation",
        "role": "Head of Ideation",
        "title": "Product Ideation Specialist",
        "reports_to": None,
        "avatar": "🌟",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "idea_generation",
            "concept_development",
            "market_analysis",
            "opportunity_assessment",
        ],
        "budget": {
            "monthly_token_limit": 1_000_000,
            "monthly_cost_limit_usd": 20.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "user_research_specialist",
        "display_name": "User Research Specialist",
        "department": "ideation",
        "role": "User Research",
        "title": "User Research Specialist",
        "reports_to": "product_ideation_specialist",
        "avatar": "👥",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "persona_creation",
            "user_needs_analysis",
            "empathy_mapping",
            "audience_segmentation",
        ],
        "budget": {
            "monthly_token_limit": 800_000,
            "monthly_cost_limit_usd": 15.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "solution_architect",
        "display_name": "Solution Architect",
        "department": "ideation",
        "role": "Solution Design",
        "title": "Solution Architect",
        "reports_to": "product_ideation_specialist",
        "avatar": "🏛️",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "solution_type_selection",
            "platform_recommendation",
            "feasibility_assessment",
            "constraint_analysis",
        ],
        "budget": {
            "monthly_token_limit": 800_000,
            "monthly_cost_limit_usd": 15.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "goal_strategist",
        "display_name": "Goal Strategist",
        "department": "ideation",
        "role": "Strategy",
        "title": "Goal Strategist",
        "reports_to": "product_ideation_specialist",
        "avatar": "🎯",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "goal_prioritization",
            "feature_ranking",
            "success_metrics",
            "okr_definition",
        ],
        "budget": {
            "monthly_token_limit": 800_000,
            "monthly_cost_limit_usd": 15.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    {
        "agent_id": "tech_stack_advisor",
        "display_name": "Tech Stack Advisor",
        "department": "ideation",
        "role": "Technology",
        "title": "Tech Stack Advisor",
        "reports_to": "product_ideation_specialist",
        "avatar": "💻",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "technology_selection",
            "stack_comparison",
            "integration_assessment",
            "scalability_planning",
        ],
        "budget": {
            "monthly_token_limit": 800_000,
            "monthly_cost_limit_usd": 15.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
    # ── Idea Agent (standalone) ───────────────────────────────
    {
        "agent_id": "idea_agent",
        "display_name": "Idea Agent",
        "department": "product",
        "role": "Slack Assistant",
        "title": "Idea Intake Agent",
        "reports_to": "product_manager",
        "avatar": "💬",
        "llm_tier": "gemini_fast",
        "capabilities": [
            "slack_interaction",
            "idea_intake",
            "clarification_questions",
            "intent_detection",
            "conversation_management",
        ],
        "budget": {
            "monthly_token_limit": 1_000_000,
            "monthly_cost_limit_usd": 20.0,
            "warning_threshold_pct": 80,
            "hard_stop": False,
        },
    },
]


def seed() -> int:
    """Upsert all agents into the registry.

    Returns the number of agents successfully upserted.
    """
    count = 0
    for agent_def in AGENTS:
        if upsert_agent(agent_def):
            count += 1
            logger.info(
                "[Seed] Upserted agent=%s dept=%s",
                agent_def["agent_id"],
                agent_def["department"],
            )
        else:
            logger.error("[Seed] Failed to upsert agent=%s", agent_def["agent_id"])

    logger.info("[Seed] Seeded %d/%d agents", count, len(AGENTS))
    return count


if __name__ == "__main__":
    seed()
