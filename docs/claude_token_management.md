# Claude Token Management and Prompt Triage Playbook

This guide provides a practical, repeatable workflow to manage token usage within context windows and a clear step-by-step method to tackle user prompts and feature requests. It is optimized for long-running agent workflows and multi-turn product conversations.

## Goals

- Keep responses accurate while staying within context limits.
- Preserve essential intent, constraints, and decisions across turns.
- Prevent silent regressions caused by stale or bloated context.
- Provide a consistent workflow for feature-level prompt handling.

## Quick Rules of Thumb

- Keep the "active working set" under 30-40% of the model context window.
- Summarize early, summarize often, and drop low-value detail.
- Prefer structured summaries over raw transcript dumps.
- Never carry entire logs, only the minimal excerpts needed for the current task.
- Always capture user intent, constraints, and known failures first.

---

## Part 1: Context Window Management

### 1.1 Context Buckets (Ranked by Importance)

1. **Current task intent**
   - What the user wants right now.
   - Any deadlines or output requirements.

2. **Hard constraints**
   - Required file formats, conventions, tests, or environments.
   - System and developer instructions.

3. **Critical state**
   - Recent code changes that affect correctness.
   - Open bugs, known regressions, error logs.

4. **Dependencies and architecture**
   - Only the modules that are relevant to the active task.

5. **Nice-to-have context**
   - Historical detail, previous discussions, less relevant logs.

When tokens are tight, drop from the bottom first.

### 1.2 The Active Working Set

Maintain a "working set" for the current task. It should include:

- The user request in a single sentence.
- Relevant code paths (function names + file paths).
- One or two crucial logs or errors.
- The next action you will take.

Everything else should be summarized or removed.

### 1.3 Context Compression Checklist

Use this list before a complex change or when the context grows:

- [ ] Summarize the conversation so far in 5-10 bullets.
- [ ] Extract a minimal list of files and functions that matter.
- [ ] Remove full logs; keep 3-8 lines max.
- [ ] Collapse repetitive test results into a single line.
- [ ] Remove redundant explanations already captured.

### 1.4 Log Handling Strategy

- Never paste full logs into the context.
- Keep only the 1-2 lines before and after the error.
- Capture:
  - Timestamp
  - Error message
  - Relevant file or function (if available)

**Example:**
```
2026-03-01 01:00:39 | INFO | events_router | Thread follow-up in C0/177... from U0...
2026-03-01 01:00:39 | ERROR | gemini_chat | The read operation timed out
```

### 1.5 Use a Rolling Summary

Maintain a rolling summary with:

- Active bugs
- Recent fixes
- Tests executed
- Open questions

Refresh every 10-15 turns or when the user changes topic.

---

## Part 2: Prompt Triage Workflow (Every User Prompt)

Use this flow for every prompt to prevent drift and control token usage.

### 2.1 Identify the Prompt Type

Classify the prompt into one of these:

- **Bug report** (errors, crashes, missing behavior)
- **Feature request** (new capability)
- **Refactor / cleanup** (structure, readability)
- **Performance** (speed, timeouts, resource usage)
- **Observability** (logs, metrics, alerts)
- **Documentation** (README, runbook, comment updates)

This determines how much code and context you need to pull in.

### 2.2 Extract the Required Inputs

Minimum required info before acting:

- Desired behavior (1 sentence)
- Current behavior (with log or error)
- Relevant location (file/function)
- Constraints (tests, platform, format)

If any are missing, ask 1-3 targeted questions.

### 2.3 Decide the Scope

- **Micro change**: single file, minimal risk. Apply directly.
- **Medium change**: touches 2-3 files. Summarize the plan first.
- **Large change**: multiple modules. Use a staged plan, confirm with the user.

### 2.4 Lock a Working Set

- Read only the files needed.
- Capture only the 2-3 function scopes needed.
- Avoid full-file dumps when a section is enough.

### 2.5 Execute + Validate

- Apply changes.
- Run the smallest relevant tests first.
- If test suite is huge, run targeted tests or report what was not run.

---

## Part 3: Feature Handling Steps (End-to-End)

Use this method to implement features with minimal context usage.

### Step 1: Define the Feature in One Sentence

Example: "Add an `update_config` intent to set Confluence/Jira keys from free-text input."

### Step 2: Identify Code Surfaces

Typical surfaces:

- Router / entry points
- Intent classification
- Handlers / services
- Persistence layer
- UI / Slack blocks
- Tests

### Step 3: Locate Single Source of Truth

Find the owner module that should define the behavior.

Example:
- Intent definitions in `tools/gemini_chat.py` and `tools/openai_chat.py`
- Routing logic in `apis/slack/_message_handler.py`

### Step 4: Add the Minimum Feature Slice

Implement just enough to make a feature viable:

- Recognize intent
- Call handler
- Persist updates
- Confirm to user

### Step 5: Add Guardrails

- Fallbacks for parsing errors
- Retry logic for transient failures
- Defensive input handling

### Step 6: Validate

- Targeted tests or logs
- One happy path, one error case

### Step 7: Summarize for User

- What changed
- Where it changed
- How to test

---

## Part 4: Token Reduction Patterns

### 4.1 Use Structured Summaries

Instead of chat transcripts:

```
Summary:
- Bug: Slack thread follow-ups ignored after TTL expiry.
- Cause: Conversation cache not refreshed on pending handlers.
- Fix: touch_thread() + session fallback in dispatcher.
- Tests: pytest tests/ (pass)
```

### 4.2 Prefer Named Anchors

Reference code by name and location rather than full blocks:

- "See `predict_and_post_next_step()` in apis/slack/_next_step.py."

### 4.3 Keep Minimal Logs

Only store the slice that proves the issue, no more.

---

## Part 5: Runbook for Silent Failures

When the bot goes silent:

1. Check event dispatcher gate: `has_conversation`, `has_pending`, `has_interactive`.
2. Verify thread cache TTL refresh.
3. Inspect LLM parse errors (`json.loads`, unexpected structures).
4. Confirm `_safe_error_reply` posts a fallback message.
5. Verify `interpret_and_act` exception handling.

---

## Part 6: Recommended Summary Template

Use this template when context is getting large:

```
Current Focus:
- ...

Known Issues:
- ...

Recent Fixes:
- ...

Files Touched:
- ...

Tests Run:
- ...
```

---

## Part 7: Example Workflow (Feature Request)

**Prompt:** "Add an option to configure more memory from thread replies."

**Steps:**
1. Classify: Feature request.
2. Inputs: Confirm target behavior + current failure log.
3. Locate handlers: `_message_handler.py`, `events_router.py`.
4. Update phrase list: add "configure more memory".
5. Ensure thread messages keep TTL alive.
6. Run tests: `pytest tests/`.
7. Summarize changes + next steps.

---

## Part 8: Common Mistakes to Avoid

- Keeping full logs in context.
- Re-reading entire files for small changes.
- Ignoring TTL and in-memory state after restart.
- Applying changes without a minimal reproduction.
- Running full test suites without need.

---

## Part 9: Checklist for Each Turn

- [ ] Intent captured in one sentence
- [ ] Constraints identified
- [ ] Minimal file reads performed
- [ ] Token-heavy logs removed or summarized
- [ ] Action plan stated
- [ ] Tests run or explicitly skipped

---

## Part 10: Optional Add-ons

If you want, I can also add:

- A short "Context Window Budget" table for different model sizes.
- A Slack-specific troubleshooting section.
- A structured logging format for prompt traceability.
