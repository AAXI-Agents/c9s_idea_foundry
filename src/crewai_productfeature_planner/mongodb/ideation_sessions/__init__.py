"""Repository for the ``ideationSessions`` collection.

Tracks interactive ideation flow sessions for the Agent Chat screen.
Each session walks a user through a 5-step flow powered by CrewAI agents:

    a) Ideation — refine paragraph → executive summary + mission
    b) Persona — identify 3-5 key user personas
    c) Solution — define solution type (mobile/web/chatbot/API)
    d) Primary Goal — mission + persona → prioritized feature goals
    e) Technical Stack — recommend technology to deliver

Standard document schema
------------------------
::

    {
        "session_id":       str,              # unique identifier (UUID hex)
        "user_id":          str,              # SSO user ID
        "project_id":       str | None,       # FK → projectConfig (linked after creation)
        "title":            str,              # auto-generated or user-set title
        "status":           str,              # active | completed | abandoned
        "current_step":     str,              # a | b | c | d | e
        "steps_data": {
            "a": { "input": ..., "output": ..., "approved": bool, "completed_at": str },
            "b": { ... },
            "c": { ... },
            "d": { ... },
            "e": { ... },
        },
        "messages": [
            {
                "id":        str,             # message UUID
                "role":      str,             # user | agent | system
                "content":   str,             # markdown text
                "step":      str,             # which flow step this belongs to
                "timestamp": str (ISO-8601),
            },
            ...
        ],
        "created_at":       str (ISO-8601),
        "updated_at":       str (ISO-8601),
        "completed_at":     str | None,

        # Tenant fields
        "enterprise_id":    str,
        "organization_id":  str,
    }
"""

from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    IDEATION_SESSIONS_COLLECTION,
    STEP_ORDER,
    advance_step,
    append_message,
    clear_step_output,
    complete_session,
    create_session,
    get_messages,
    get_session,
    list_sessions,
    rollback_step,
    save_step_data,
    update_session_status,
)

__all__ = [
    "IDEATION_SESSIONS_COLLECTION",
    "STEP_ORDER",
    "advance_step",
    "append_message",
    "clear_step_output",
    "complete_session",
    "create_session",
    "get_messages",
    "get_session",
    "list_sessions",
    "rollback_step",
    "save_step_data",
    "update_session_status",
]
