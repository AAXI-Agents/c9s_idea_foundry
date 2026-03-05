"""Late-bound handler proxies for the Slack events router.

These resolve handler functions through ``events_router`` at call time
so that ``unittest.mock.patch("...events_router._<name>")`` in tests
always takes effect.  We import ``events_router`` lazily to avoid
circular imports (events_router imports the message handler module).
"""

from __future__ import annotations

import sys

_ER_MODULE = "crewai_productfeature_planner.apis.slack.events_router"


def _er():
    """Return the events_router module (lazy)."""
    return sys.modules[_ER_MODULE]


def _prompt_project_selection(channel, thread_ts, user):
    return _er()._prompt_project_selection(channel, thread_ts, user)


def _handle_switch_project(channel, thread_ts, user):
    return _er()._handle_switch_project(channel, thread_ts, user)


def _handle_end_session(channel, thread_ts, user):
    return _er()._handle_end_session(channel, thread_ts, user)


def _handle_current_project(channel, thread_ts, user, session):
    return _er()._handle_current_project(channel, thread_ts, user, session)


def _handle_configure_memory(channel, thread_ts, user, session):
    return _er()._handle_configure_memory(channel, thread_ts, user, session)


def _handle_update_config(channel, thread_ts, user, session, **kwargs):
    return _er()._handle_update_config(channel, thread_ts, user, session, **kwargs)


def _handle_create_project_intent(channel, thread_ts, user):
    return _er()._handle_create_project_intent(channel, thread_ts, user)


def _kick_off_prd_flow(**kwargs):
    return _er()._kick_off_prd_flow(**kwargs)


def _handle_publish_intent(channel, thread_ts, user, send_tool):
    return _er()._handle_publish_intent(channel, thread_ts, user, send_tool)


def _handle_list_ideas(channel, thread_ts, user, session):
    return _er()._handle_list_ideas(channel, thread_ts, user, session)


def _handle_list_products(channel, thread_ts, user, session):
    return _er()._handle_list_products(channel, thread_ts, user, session)


def _handle_check_publish_intent(channel, thread_ts, user, send_tool):
    return _er()._handle_check_publish_intent(channel, thread_ts, user, send_tool)


def _handle_resume_prd(channel, thread_ts, user, send_tool, project_id=None, idea_number=None):
    return _er()._handle_resume_prd(channel, thread_ts, user, send_tool, project_id=project_id, idea_number=idea_number)


def _handle_restart_prd(channel, thread_ts, user, send_tool, event_ts, project_id=None, idea_number=None):
    return _er()._handle_restart_prd(channel, thread_ts, user, send_tool, event_ts, project_id=project_id, idea_number=idea_number)


def _reply(channel, thread_ts, text):
    return _er()._reply(channel, thread_ts, text)
