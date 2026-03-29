# UX Designer

> Converts product vision into structured design specifications and Figma prototypes through a 2-phase collaborative design flow.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research |
| **Model Env Var** | `GEMINI_UX_DESIGNER_MODEL` → `GEMINI_RESEARCH_MODEL` → `DEFAULT_GEMINI_RESEARCH_MODEL` |
| **Tools** | FigmaMakeTool |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Introduced** | v0.20.0 (refactored v0.41.0) |
| **Source** | `agents/ux_designer/` |

---

## Role

> Senior UX Designer & Figma Prototyping Specialist

## Goal

Transform product executive summaries into structured, production-ready Figma Make prompts that generate clickable prototypes with reusable components, proper design tokens, and complete user flows.

## Backstory

You are a world-class UX designer with 15+ years of experience shipping products at scale. You think in design systems, not individual screens. Every component you create is reusable. You have deep expertise in: information architecture, component-driven design, design tokens, responsive layout grids, accessibility (WCAG 2.1 AA), interaction design, Figma auto-layout, variants, and component properties.

---

## Agent Variants

### UX Designer (Phase 1 lead)

- **Purpose**: Generate comprehensive Figma Make prompt covering design system, user flows, components, layout, interactions
- **Tools**: FigmaMakeTool

### Design Partner (v0.41.0)

- **Purpose**: Collaborates with UX Designer on the initial design draft using gstack design-consultation methodology. Covers product context, aesthetic direction, typography, color, spacing, layout, motion, shadows, component patterns, interaction states, and CSS token export. Includes AI slop avoidance blacklist.
- **Tools**: None
- **Source**: `agents/ux_designer/config/design_partner.yaml`

### Senior Designer (v0.41.0)

- **Purpose**: Reviews and finalizes the initial design draft using gstack plan-design-review methodology. Applies 7-pass review (information architecture, interaction states, user journey, AI slop, design system alignment, responsive/accessibility, unresolved decisions) with before/after scoring. Produces the production-ready design specification.
- **Tools**: None
- **Source**: `agents/ux_designer/config/senior_designer.yaml`

---

## Tasks

### `generate_figma_make_prompt_task`

Generate comprehensive Figma Make prompt covering:

- **Design system**: colour palette, typography, spacing, border radius, shadows, icons
- **User flows**: entry points, key screens, success/error/empty/loading states, edge cases
- **Reusable components**: names, variants, auto-layout, content slots
- **Page structure**: layout grid, responsive behaviour
- **Interaction & navigation**: click targets, transitions, scroll behaviour, modals

**Expected output**: Complete design prompt prefixed with `FIGMA_PROMPT:`, plus:
- `FIGMA_URL:<url>` (if Figma creation succeeded)
- `FIGMA_ERROR:<message>` (if failed)
- `FIGMA_SKIPPED:<reason>` (if skipped)

---

## Tools

| Tool | Purpose |
|------|---------|
| `FigmaMakeTool` | Generate Figma designs from structured design prompts |

---

## 2-Phase Design Flow (v0.41.0)

| Phase | Agents | Purpose |
|-------|--------|---------|
| Phase 1 | UX Designer + Design Partner | Collaborative initial design draft |
| Phase 2 | Senior Designer | 7-pass review and finalization |

---

## PRD Flow Phase

**Post-PRD** — Triggered from finalization after all sections are approved. Consumes the Executive Product Summary.

---

## Source Files

- `agents/ux_designer/config/agent.yaml` — role, goal, backstory
- `agents/ux_designer/config/tasks.yaml` — task definitions
- `agents/ux_designer/config/design_partner.yaml` — Design Partner agent config
- `agents/ux_designer/config/senior_designer.yaml` — Senior Designer agent config
- `agents/ux_designer/agent.py` — agent factory functions

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]]
