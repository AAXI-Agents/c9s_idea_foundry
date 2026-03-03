"""PRD section order and key constants."""

SECTION_ORDER: list[tuple[str, str]] = [
    ("executive_summary", "Executive Summary"),
    ("problem_statement", "Problem Statement"),
    ("user_personas", "User Personas"),
    ("functional_requirements", "Functional Requirements"),
    ("no_functional_requirements", "Non-Functional Requirements"),
    ("edge_cases", "Edge Cases"),
    ("error_handling", "Error Handling"),
    ("success_metrics", "Success Metrics"),
    ("dependencies", "Dependencies"),
    ("assumptions", "Assumptions"),
]

SECTION_KEYS: list[str] = [key for key, _ in SECTION_ORDER]
