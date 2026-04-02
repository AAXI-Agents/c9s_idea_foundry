---
tags:
  - design
  - ux
---

# Design System — CrewAI Product Feature Planner

> **Role**: Design Partner (gstack `/design-consultation`)
> **Date**: 2026-03-25
> **Status**: Initial Draft — pending Senior Designer review

---

## Product Context

- **What this is:** An AI-powered PRD generation engine that transforms raw product ideas into implementation-ready Product Requirements Documents using multi-agent CrewAI orchestration (Gemini + OpenAI LLMs)
- **Who it's for:** Product Managers, Startup Founders, Enterprise Product Teams, and Technical Writers
- **Space/industry:** Developer Tools / Product Management / AI-Assisted Productivity
- **Project type:** Web app dashboard with Slack bot integration, CLI, and REST API
- **Comparable products:** monday.com work management, Linear, Notion AI, Productboard
- **Primary UI surface:** Slack Block Kit (current), with future web dashboard planned

---

## Aesthetic Direction

- **Direction:** Industrial/Utilitarian — influenced by monday.com's Vibe Design System
- **Decoration level:** Intentional — clean surfaces with purposeful color for status hierarchy and workflow stages
- **Mood:** Productive, trustworthy, organized. The interface should feel like a well-oiled machine — not flashy, but deeply functional. Like monday.com: dense but readable, colorful but purposeful, with a calm surface hierarchy that lets the work take center stage.
- **Reference system:** [monday.com Vibe Design System v4](https://vibe.monday.com/) — the source of truth for all tokens, components, and patterns

### Why monday.com's Vibe

monday.com is the gold standard for work management UIs that handle complex, multi-stage workflows — exactly what PRD generation is. Their design system excels at:

1. **Status color language** — 40+ named status colors (done-green, working-orange, stuck-red) that communicate state instantly
2. **Dense but readable** — Information density without visual noise; utility language over mood/brand
3. **Board/table paradigm** — Structured data views that map perfectly to PRD sections, idea lists, and pipeline stages
4. **Calm surface hierarchy** — White/light surfaces with strong typography and few accent colors

---

## Typography

Based on monday.com Vibe v4 tokens:

- **Display/Hero:** Poppins — monday.com's title font family. Bold weight, tight letter-spacing (-0.5px). Used for page headings and hero text.
- **Body:** Figtree — monday.com's primary body font. Clean, geometric sans-serif with excellent readability at 14-16px. Replaced Roboto in Vibe v3→v4 upgrade.
- **UI/Labels:** Figtree — consistent with body for labels, buttons, navigation
- **Data/Tables:** Figtree with `font-variant-numeric: tabular-nums` — ensures aligned columns in PRD section tables, idea lists, and status dashboards
- **Code:** JetBrains Mono — for code snippets, run IDs, and technical identifiers
- **Loading:** Google Fonts CDN — `Poppins:wght@300;500;600;700` + `Figtree:wght@300;400;500;600;700`

### Type Scale (from Vibe v4 tokens)

| Token | Size | Line Height | Weight | Family | Usage |
|-------|------|-------------|--------|--------|-------|
| `--font-h1` | 30px | 42px | 500 (bold) | Poppins | Page titles, hero headings |
| `--font-h2` | 24px | 32px | 500 (bold) | Poppins | Section headings |
| `--font-h3` | 24px | 32px | 300 (light) | Poppins | Subheadings (light weight) |
| `--font-h4` | 18px | 24px | 500 (bold) | Poppins | Card titles, panel headings |
| `--font-h5` | 16px | 24px | 500 (bold) | Figtree | Group headers, small headings |
| `--font-text1` | 16px | 22px | 400 | Figtree | Body text, descriptions |
| `--font-text2` | 14px | 20px | 400 | Figtree | Default UI text, table cells |
| `--font-text3` | 12px | 16px | 400 | Figtree | Captions, metadata, timestamps |
| `--font-subtext` | 14px | 18px | 400 | Figtree | Secondary labels |
| `--font-general-label` | 14px | 24px | 400 | Figtree | Form labels, column headers |

### Letter Spacing

| Level | Spacing |
|-------|---------|
| H1 | -0.5px |
| H2 | -0.1px |
| H3 | -0.1px |
| Body/UI | 0 (normal) |

---

## Color

- **Approach:** Balanced — one strong primary (#0073EA brand blue) + rich semantic/status palette for workflow stages

### Core Palette (Vibe Light Theme)

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary-color` | `#0073EA` | Primary actions, links, active states — monday.com "basic blue" |
| `--primary-hover-color` | `#0060B9` | Hover on primary buttons/links |
| `--primary-selected-color` | `#CCE5FF` | Selected rows, active filters |
| `--primary-highlighted-color` | `#F0F7FF` | Subtle highlight backgrounds |
| `--primary-text-color` | `#323338` | Primary text — "mud black" |
| `--secondary-text-color` | `#676879` | Secondary text — "asphalt" |
| `--text-color-on-primary` | `#FFFFFF` | Text on blue backgrounds |

### Backgrounds & Surfaces

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary-background-color` | `#FFFFFF` | Main content area |
| `--allgrey-background-color` | `#F6F7FB` | Page background, sidebar — "riverstone gray" |
| `--ui-background-color` | `#E7E9EF` | Subtle UI separators |
| `--inverted-color-background` | `#323338` | Dark surfaces, tooltips |
| `--backdrop-color` | `rgba(41, 47, 76, 0.7)` | Modal overlays |

### Borders & Lines

| Token | Hex | Usage |
|-------|-----|-------|
| `--ui-border-color` | `#C3C6D4` | Input borders, table lines — "wolf gray" |
| `--layout-border-color` | `#D0D4E4` | Layout separators, card borders |

### Status Colors (Workflow-Critical)

These map directly to PRD pipeline stages — the heart of the product's visual language:

| Status | Token | Hex | PRD Usage |
|--------|-------|-----|-----------|
| Done/Complete | `--color-done-green` | `#00C875` | Completed PRD sections, published ideas |
| Working/In Progress | `--color-working_orange` | `#FDAB3D` | Active drafting, agent processing |
| Stuck/Error | `--color-stuck-red` | `#DF2F4A` | Failed sections, errors, blocked flows |
| Warning | `--warning-color` | `#FFCB00` | Pending approval, attention needed |
| Positive/Success | `--positive-color` | `#00854D` | Confluence published, Jira created |
| Negative/Danger | `--negative-color` | `#D83A52` | Cancel, delete, destructive actions |
| Link | `--link-color` | `#1F76C2` | Hyperlinks, clickable references |

### Extended Status Colors (for PRD Pipeline Stages)

| Stage | Color Name | Hex | Usage |
|-------|------------|-----|-------|
| Idea Submitted | bright-blue | `#579BFC` | New idea, awaiting refinement |
| Idea Refining | working-orange | `#FDAB3D` | AI agent iterating on idea |
| Requirements | egg-yolk | `#FFCB00` | Requirements breakdown phase |
| Exec Summary | lipstick | `#FF5AC4` | Executive summary drafting |
| Section Drafting | purple | `#9D50DD` | Section generation in progress |
| Review/Critique | indigo | `#5559DF` | Agent critique cycle |
| Approved | done-green | `#00C875` | Section/idea approved |
| Publishing | dark-blue | `#007EB5` | Confluence/Jira publishing |
| Complete | grass-green | `#037F4C` | Fully delivered |
| Failed/Paused | stuck-red | `#DF2F4A` | Error or paused state |

### Brand Colors (monday.com brand palette)

| Name | Hex | Note |
|------|-----|------|
| brand-blue | `#00A9FF` | — |
| brand-charcoal | `#2B2C5C` | — |
| brand-gold | `#FFCC00` | — |
| brand-green | `#11DD80` | — |
| brand-iris | `#595AD4` | — |
| brand-purple | `#A358D0` | — |
| brand-red | `#F74875` | — |

### Dark Mode Strategy

monday.com uses a dedicated dark theme with inverted surfaces while preserving color semantics. Strategy:
- Surfaces invert: `#FFFFFF` → `#181B34` (deep navy-charcoal)
- Text inverts: `#323338` → `#D5D8DF`
- Status colors remain the same (already high-contrast on dark)
- Primary blue stays: `#0073EA` (sufficient contrast on dark surfaces)
- Reduce saturation 10-15% on background colors only

---

## Spacing

Based on Vibe v4 spacing tokens — 2px base unit with purposeful density:

| Token | Value | Usage |
|-------|-------|-------|
| `--space-2` | 2px | Hairline gaps, icon-to-text inline |
| `--space-4` | 4px | Tight internal padding, badge spacing |
| `--space-8` | 8px | Default component internal padding |
| `--space-12` | 12px | Compact list item spacing |
| `--space-16` | 16px | Standard padding, card internal |
| `--space-20` | 20px | Generous internal padding |
| `--space-24` | 24px | Section gaps within cards |
| `--space-32` | 32px | Between-card gaps |
| `--space-40` | 40px | Major section separation |
| `--space-48` | 48px | Page-level separation |
| `--space-64` | 64px | Hero/feature section gaps |
| `--space-80` | 80px | Maximum whitespace (used sparingly) |

### Density: Comfortable-Dense

monday.com is famous for information density that doesn't feel cramped. For PRD Planner:
- **Table rows:** 36-40px height (space-8 vertical padding + text2 at 14px)
- **List items:** 32-36px height
- **Card padding:** space-16 internal, space-8 between elements inside
- **Section gaps:** space-32 between content blocks
- **Page padding:** space-24 horizontal, space-16 top

---

## Layout

- **Approach:** Grid-disciplined — strict columns, predictable alignment (monday.com board paradigm)
- **Grid:** Sidebar (240-280px fixed) + Main content (fluid, 12-column grid within)
- **Max content width:** 1440px (with side padding), fluid below
- **Breakpoints:**
  - Desktop: 1200px+ (sidebar + full board view)
  - Tablet: 768-1199px (collapsible sidebar, stacked columns)
  - Mobile: <768px (bottom nav, single column, card-based)

### Border Radius (Vibe tokens)

| Token | Value | Usage |
|-------|-------|-------|
| `--border-radius-small` | 4px | Buttons, inputs, badges, chips |
| `--border-radius-medium` | 8px | Cards, dialogs, dropdowns |
| `--border-radius-big` | 16px | Large containers, hero cards |
| `full` | 9999px | Avatars, pills, circular elements |

### Key Layout Components

```
┌─────────────────────────────────────────────────────────┐
│ Top Bar (56px)  Logo | Workspace | Search | User Avatar │
├────────────┬────────────────────────────────────────────┤
│            │ Board Header                               │
│  Sidebar   │ ┌─── Group: Active Ideas ───────────────┐  │
│  (260px)   │ │ [Status] [Idea Name] [Phase] [Agent]  │  │
│            │ │ 🟢 Dashboard v2    Drafting   PM      │  │
│ Projects   │ │ 🟡 Auth Module     Review     QA      │  │
│ Ideas      │ │ 🔴 API Gateway     Stuck      -       │  │
│ PRDs       │ └───────────────────────────────────────┘  │
│ Publishing │ ┌─── Group: Completed ──────────────────┐  │
│ Settings   │ │ ✅ User Personas   Published  Done    │  │
│            │ └───────────────────────────────────────┘  │
├────────────┴────────────────────────────────────────────┤
│ Status Bar: 3 Active | 5 Complete | 1 Failed            │
└─────────────────────────────────────────────────────────┘
```

---

## Motion

Based on Vibe v4 motion tokens — productive and restrained:

- **Approach:** Minimal-functional — motion aids comprehension, never decorates
- **Philosophy:** "Productive" for micro-interactions (70-150ms), "Expressive" for meaningful transitions (250-400ms)

| Token | Duration | Usage |
|-------|----------|-------|
| `--motion-productive-short` | 70ms | Hover states, toggle switches |
| `--motion-productive-medium` | 100ms | Button press, checkbox, focus ring |
| `--motion-productive-long` | 150ms | Dropdown open, tooltip appear |
| `--motion-expressive-short` | 250ms | Panel slide, card expand |
| `--motion-expressive-long` | 400ms | Page transitions, modal open/close |

### Easing Curves

| Token | Curve | Usage |
|-------|-------|-------|
| `--motion-timing-enter` | `cubic-bezier(0, 0, 0.35, 1)` | Elements entering view |
| `--motion-timing-exit` | `cubic-bezier(0.4, 0, 1, 1)` | Elements leaving view |
| `--motion-timing-transition` | `cubic-bezier(0.4, 0, 0.2, 1)` | State changes, transforms |
| `--motion-timing-emphasize` | `cubic-bezier(0, 0, 0.2, 1.4)` | Bounce/overshoot for emphasis |

---

## Shadows (Vibe tokens)

| Level | Value | Usage |
|-------|-------|-------|
| `--box-shadow-xs` | `0px 4px 6px -4px rgba(0,0,0,0.1)` | Subtle elevation, sticky headers |
| `--box-shadow-small` | `0px 4px 8px rgba(0,0,0,0.2)` | Dropdowns, tooltips |
| `--box-shadow-medium` | `0px 6px 20px rgba(0,0,0,0.2)` | Cards on hover, dialogs |
| `--box-shadow-large` | `0px 15px 50px rgba(0,0,0,0.3)` | Modals, overlays |

---

## Component Patterns

### Buttons

Follow monday.com's button hierarchy:

| Type | Background | Text | Border Radius | Height |
|------|-----------|------|---------------|--------|
| Primary | `#0073EA` | `#FFFFFF` | 4px | 40px |
| Secondary | `transparent` | `#323338` | 4px | 40px |
| Tertiary | `transparent` | `#0073EA` | 4px | 40px |
| Danger | `#D83A52` | `#FFFFFF` | 4px | 40px |
| Disabled | `rgba(50,51,56,0.12)` | `rgba(50,51,56,0.38)` | 4px | 40px |

Sizes: Small (32px), Medium (40px), Large (48px)

### Status Badges/Chips

Colored background pills matching the status color palette:

```css
.status-badge {
  padding: 4px 8px;
  border-radius: 9999px;
  font: var(--font-text3-bold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
```

### Cards

```css
.card {
  background: var(--primary-background-color);
  border: 1px solid var(--layout-border-color);
  border-radius: var(--border-radius-medium);
  padding: var(--space-16);
  transition: box-shadow var(--motion-productive-long) var(--motion-timing-transition);
}
.card:hover {
  box-shadow: var(--box-shadow-medium);
}
```

### Data Tables (Board View)

The core UI pattern — mirrors monday.com's board:

```css
.board-header {
  background: var(--allgrey-background-color);
  font: var(--font-text2-bold);
  color: var(--secondary-text-color);
  padding: var(--space-8) var(--space-16);
  border-bottom: 1px solid var(--layout-border-color);
}
.board-row {
  padding: var(--space-8) var(--space-16);
  border-bottom: 1px solid var(--layout-border-color);
  transition: background var(--motion-productive-short);
}
.board-row:hover {
  background: var(--primary-background-hover-color);
}
.group-header {
  font: var(--font-h5);
  padding: var(--space-8) var(--space-16);
  border-left: 4px solid var(--color-bright-blue); /* group indicator color */
}
```

---

## Slack Block Kit Mapping

Since the primary interface is Slack, here's how the design system maps to Block Kit:

| Design Token | Slack Equivalent |
|-------------|-----------------|
| Primary button | `style: "primary"` (green in Slack) |
| Danger button | `style: "danger"` (red in Slack) |
| Status colors | Emoji prefixes: ✅ 🟡 🔴 ⚙️ 🔵 |
| Section separator | `type: "divider"` |
| Card | `type: "section"` with `accessory` |
| Table | Multiple `section` blocks with `fields` |
| Hero heading | `type: "header"` |
| Metadata | `type: "context"` with `mrkdwn` elements |

---

## Figma Make — Design Token Export

For Figma Make import, the design tokens are expressed as CSS custom properties:

```css
:root {
  /* Typography */
  --font-family: Figtree, Roboto, Noto Sans Hebrew, Noto Kufi Arabic, Noto Sans JP, sans-serif;
  --title-font-family: Poppins, Roboto, Noto Sans Hebrew, Noto Kufi Arabic, Noto Sans JP, sans-serif;

  /* Primary Colors */
  --primary-color: #0073ea;
  --primary-hover-color: #0060b9;
  --primary-selected-color: #cce5ff;
  --primary-text-color: #323338;
  --secondary-text-color: #676879;
  --text-color-on-primary: #ffffff;

  /* Backgrounds */
  --primary-background-color: #ffffff;
  --allgrey-background-color: #f6f7fb;
  --inverted-color-background: #323338;

  /* Borders */
  --ui-border-color: #c3c6d4;
  --layout-border-color: #d0d4e4;

  /* Status */
  --color-done-green: #00c875;
  --color-working_orange: #fdab3d;
  --color-stuck-red: #df2f4a;
  --color-egg_yolk: #ffcb00;
  --positive-color: #00854d;
  --negative-color: #d83a52;

  /* Spacing */
  --space-4: 4px;
  --space-8: 8px;
  --space-12: 12px;
  --space-16: 16px;
  --space-24: 24px;
  --space-32: 32px;
  --space-40: 40px;

  /* Border Radius */
  --border-radius-small: 4px;
  --border-radius-medium: 8px;
  --border-radius-big: 16px;

  /* Shadows */
  --box-shadow-xs: 0px 4px 6px -4px rgba(0, 0, 0, 0.1);
  --box-shadow-small: 0px 4px 8px rgba(0, 0, 0, 0.2);
  --box-shadow-medium: 0px 6px 20px rgba(0, 0, 0, 0.2);
  --box-shadow-large: 0px 15px 50px rgba(0, 0, 0, 0.3);

  /* Motion */
  --motion-productive-short: 70ms;
  --motion-productive-medium: 100ms;
  --motion-productive-long: 150ms;
  --motion-expressive-short: 250ms;
  --motion-expressive-long: 400ms;
  --motion-timing-enter: cubic-bezier(0, 0, 0.35, 1);
  --motion-timing-exit: cubic-bezier(0.4, 0, 1, 1);
  --motion-timing-transition: cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-25 | Use monday.com Vibe v4 as design foundation | User requested monday.com look and feel; Vibe is the official open-source design system with well-documented tokens |
| 2026-03-25 | Figtree as body font, Poppins for titles | Direct from Vibe v4 tokens — Figtree replaced Roboto in the v3→v4 upgrade |
| 2026-03-25 | 10-color PRD pipeline status mapping | Maps each pipeline stage to a distinct Vibe status color for instant visual recognition |
| 2026-03-25 | Board/table as primary layout paradigm | monday.com's core pattern; maps naturally to idea lists, PRD sections, and pipeline views |
| 2026-03-25 | Comfortable-dense spacing | Matches monday.com's information-dense-yet-readable approach; appropriate for a data-heavy product management tool |
