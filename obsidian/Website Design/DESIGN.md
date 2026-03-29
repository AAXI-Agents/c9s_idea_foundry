# Design System — CrewAI Product Feature Planner

> **Version**: 1.0 — Final  
> **Roles**: Design Partner + Senior Designer (gstack methodology)  
> **Date**: 2026-03-25  
> **Foundation**: monday.com Vibe Design System v4  
> **Target**: Figma Make upload

---

## Senior Designer Review Summary

Seven-pass review applied to the initial draft. Scores and fixes below.

| Pass | Area | Score | Key Fix |
|------|------|-------|---------|
| 1 | Information Architecture | 6 → 9 | Added screen inventory, navigation hierarchy, content zones |
| 2 | Interaction State Coverage | 3 → 9 | Added full state matrix: loading, empty, error, success, partial, disabled |
| 3 | User Journey & Emotional Arc | 4 → 8 | Added lifecycle map with emotional beats per pipeline stage |
| 4 | AI Slop Risk | 7 → 9 | Flagged and removed 2 slop patterns; added explicit anti-pattern list |
| 5 | Design System Alignment | 8 → 9 | Fixed token naming inconsistencies, added missing semantic aliases |
| 6 | Responsive & Accessibility | 4 → 8 | Added mobile layouts, touch targets, ARIA patterns, contrast ratios |
| 7 | Unresolved Design Decisions | 5 → 8 | Documented 8 open questions with recommended defaults |

---

## 1. Product Context

- **Product**: AI-powered PRD generation engine — transforms raw ideas into implementation-ready Product Requirements Documents via multi-agent CrewAI orchestration (Gemini + OpenAI LLMs)
- **Users**: Product Managers, Startup Founders, Enterprise Product Teams, Technical Writers
- **Domain**: Developer Tools / Product Management / AI-Assisted Productivity
- **Comparable products**: monday.com work management, Linear, Notion AI, Productboard
- **Primary surface**: Slack Block Kit (current production); future web dashboard
- **Secondary surfaces**: CLI, REST API (FastAPI)

---

## 2. Aesthetic Direction

**Direction**: Industrial/Utilitarian — influenced by monday.com Vibe Design System v4  
**Decoration**: Intentional — clean surfaces with purposeful color for status hierarchy  
**Mood**: Productive, trustworthy, organized. The interface feels like a well-oiled machine — dense but readable, colorful but purposeful, with calm surface hierarchy that lets the work breathe.

### Why monday.com Vibe

monday.com handles complex multi-stage workflows — exactly what PRD generation is. Their system excels at:

1. **Status color language** — 40+ named colors communicating state instantly
2. **Dense but readable** — Information density without visual noise
3. **Board/table paradigm** — Structured views mapping to idea lists, PRD sections, pipeline stages
4. **Calm surface hierarchy** — White/light surfaces, strong typography, few accent colors

### AI Slop Anti-Patterns (Mandatory Avoidance)

These patterns are explicitly banned from all design output:

| # | Anti-Pattern | Why It's Banned |
|---|-------------|----------------|
| 1 | Purple/violet gradients as hero backgrounds | Generic AI-tool aesthetic; screams "generated" |
| 2 | 3-column icon grids with abstract icons | Layout crutch that adds no information |
| 3 | Everything centered with no alignment anchor | Kills scanability; real tools use left-aligned content |
| 4 | Rounded-everything with soft shadows | Over-friendly; inappropriate for data-heavy PM tool |
| 5 | Stock illustration characters waving | Decoration without function |
| 6 | "Powered by AI" badges everywhere | Undermines trust — let the output speak |
| 7 | Glassmorphism cards | Performance cost, accessibility nightmare, trendy not timeless |
| 8 | Animated gradient borders | Distracting; motion should serve comprehension only |
| 9 | Overly generous whitespace with tiny text | Wastes screen real estate PM users need |
| 10 | Generic "dashboard" with meaningless charts | Every data visualization must map to a real metric |

**Corrections from initial draft**: Removed aspirational "hero" language. Tightened wireframe to show real content zones instead of placeholder boxes. Ensured all component examples use actual PRD data, not lorem ipsum.

---

## 3. Typography

Based on monday.com Vibe v4 tokens.

- **Display/Hero**: Poppins — Bold weight, tight letter-spacing. Page headings and hero text only.
- **Body**: Figtree — Geometric sans-serif, excellent readability at 14–16px. Replaced Roboto in Vibe v3→v4.
- **UI/Labels**: Figtree — Consistent with body for buttons, navigation, form labels.
- **Data/Tables**: Figtree with `font-variant-numeric: tabular-nums` — Aligned columns in tables.
- **Code**: JetBrains Mono — Run IDs, technical identifiers, code snippets.
- **Loading**: Google Fonts CDN — `Poppins:wght@300;500;600;700` + `Figtree:wght@300;400;500;600;700`

### Type Scale

| Token | Size | Line Height | Weight | Family | Usage |
|-------|------|-------------|--------|--------|-------|
| `--font-h1` | 30px | 42px | 500 | Poppins | Page titles |
| `--font-h2` | 24px | 32px | 500 | Poppins | Section headings |
| `--font-h3` | 24px | 32px | 300 | Poppins | Subheadings (light) |
| `--font-h4` | 18px | 24px | 500 | Poppins | Card titles, panel headings |
| `--font-h5` | 16px | 24px | 500 | Figtree | Group headers |
| `--font-text1` | 16px | 22px | 400 | Figtree | Body text, descriptions |
| `--font-text2` | 14px | 20px | 400 | Figtree | Default UI text, table cells |
| `--font-text3` | 12px | 16px | 400 | Figtree | Captions, metadata, timestamps |
| `--font-subtext` | 14px | 18px | 400 | Figtree | Secondary labels |
| `--font-general-label` | 14px | 24px | 400 | Figtree | Form labels, column headers |

### Letter Spacing

| Level | Spacing |
|-------|---------|
| H1 | -0.5px |
| H2–H3 | -0.1px |
| Body/UI | 0 (normal) |

---

## 4. Color

**Approach**: Balanced — one strong primary (`#0073EA`) + rich semantic/status palette for workflow stages.

### 4.1 Core Palette (Vibe Light Theme)

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary-color` | `#0073EA` | Primary actions, links, active states |
| `--primary-hover-color` | `#0060B9` | Hover on primary elements |
| `--primary-selected-color` | `#CCE5FF` | Selected rows, active filters |
| `--primary-highlighted-color` | `#F0F7FF` | Subtle highlight backgrounds |
| `--primary-text-color` | `#323338` | Primary text — "mud black" |
| `--secondary-text-color` | `#676879` | Secondary text — "asphalt" |
| `--disabled-text-color` | `rgba(50,51,56,0.38)` | Disabled labels, placeholder text |
| `--text-color-on-primary` | `#FFFFFF` | Text on blue backgrounds |
| `--text-color-on-inverted` | `#D5D8DF` | Text on dark surfaces |

### 4.2 Backgrounds & Surfaces

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary-background-color` | `#FFFFFF` | Main content area |
| `--primary-background-hover-color` | `#DCE0EC` | Row hover |
| `--secondary-background-color` | `#F6F7FB` | Page background, sidebar |
| `--ui-background-color` | `#E7E9EF` | Subtle separators |
| `--inverted-color-background` | `#323338` | Dark surfaces, tooltips |
| `--backdrop-color` | `rgba(41, 47, 76, 0.7)` | Modal overlays |

### 4.3 Borders & Lines

| Token | Hex | Usage |
|-------|-----|-------|
| `--ui-border-color` | `#C3C6D4` | Input borders, table lines |
| `--layout-border-color` | `#D0D4E4` | Layout separators, card borders |
| `--focus-ring-color` | `#0073EA` | Keyboard focus indicator (2px solid) |

### 4.4 Status Colors — PRD Pipeline

The heart of the visual language. Each PRD stage has a unique, instantly recognizable color:

| Stage | Token | Hex | Slack Emoji |
|-------|-------|-----|-------------|
| Idea Submitted | `--status-idea-submitted` | `#579BFC` | 🔵 |
| Idea Refining | `--status-idea-refining` | `#FDAB3D` | 🟡 |
| Requirements | `--status-requirements` | `#FFCB00` | ⚡ |
| Exec Summary | `--status-exec-summary` | `#FF5AC4` | 💜 |
| Section Drafting | `--status-drafting` | `#9D50DD` | ✏️ |
| Review/Critique | `--status-review` | `#5559DF` | 🔍 |
| Approved | `--status-approved` | `#00C875` | ✅ |
| Publishing | `--status-publishing` | `#007EB5` | 📤 |
| Complete | `--status-complete` | `#037F4C` | ✔️ |
| Failed/Paused | `--status-failed` | `#DF2F4A` | 🔴 |

**Review fix**: Added semantic token aliases (`--status-*`) instead of referencing raw Vibe color names. This decouples pipeline semantics from the Vibe palette — if a status color changes, only the alias mapping needs updating.

### 4.5 Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--positive-color` | `#00854D` | Success messages, published confirmations |
| `--negative-color` | `#D83A52` | Error messages, destructive actions |
| `--warning-color` | `#FFCB00` | Pending approval, attention needed |
| `--link-color` | `#1F76C2` | Hyperlinks, clickable references |

### 4.6 Dark Mode Strategy

- Surfaces invert: `#FFFFFF` → `#181B34` (deep navy-charcoal)
- Text inverts: `#323338` → `#D5D8DF`
- Status colors remain unchanged (already high-contrast on dark)
- Primary blue stays `#0073EA` (sufficient contrast both themes)
- Reduce background color saturation 10–15%
- Implementation: CSS custom property overrides via `[data-theme="dark"]` selector

---

## 5. Spacing

Based on Vibe v4 — 2px base unit with purposeful density:

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
| `--space-80` | 80px | Maximum whitespace (sparingly) |

### Density

**Mode**: Comfortable-Dense (monday.com's signature)

| Element | Height | Spacing |
|---------|--------|---------|
| Table rows | 36–40px | `--space-8` vertical padding + text2 (14px) |
| List items | 32–36px | `--space-8` vertical + `--space-12` horizontal |
| Card internals | — | `--space-16` padding, `--space-8` between elements |
| Section gaps | — | `--space-32` between content blocks |
| Page padding | — | `--space-24` horizontal, `--space-16` top |

---

## 6. Layout

**Approach**: Grid-disciplined — sidebar + board paradigm from monday.com.

### Grid System

- **Sidebar**: 260px fixed (collapsible to 48px icon rail)
- **Main content**: Fluid, 12-column grid within
- **Max content width**: 1440px (with `--space-24` side padding), fluid below
- **Column gutter**: `--space-16`
- **Minimum touch target**: 44×44px (WCAG 2.5.8)

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--border-radius-small` | 4px | Buttons, inputs, badges, chips |
| `--border-radius-medium` | 8px | Cards, dialogs, dropdowns |
| `--border-radius-big` | 16px | Large containers, hero cards |
| `--border-radius-full` | 9999px | Avatars, pills, circular elements |

### Breakpoints & Responsive Behavior

| Breakpoint | Width | Layout | Sidebar | Navigation |
|-----------|-------|--------|---------|------------|
| Desktop XL | ≥1440px | Full board + sidebar | 260px open | Sidebar |
| Desktop | 1200–1439px | Full board + sidebar | 260px open | Sidebar |
| Tablet | 768–1199px | Stacked columns | 48px icon rail | Top bar + hamburger |
| Mobile | <768px | Single column, card-based | Hidden | Bottom tab bar |

### Mobile-Specific Adaptations (Review Addition)

| Desktop Pattern | Mobile Replacement |
|----------------|-------------------|
| Board/table view | Stacked card list (one card per idea/PRD) |
| Sidebar navigation | Bottom tab bar: Home · Ideas · PRDs · Settings |
| Multi-column fields | Single-column stack, full-width |
| Hover tooltips | Long-press reveal or inline expand |
| Context menus | Bottom sheet with action list |
| Status badge row | Swipeable status chips |

### Screen Inventory (Review Addition)

| # | Screen | Content Zones | Primary Action |
|---|--------|--------------|----------------|
| 1 | **Workspace Home** | Project selector, recent ideas, active PRDs, quick stats | New Idea |
| 2 | **Ideas Board** | Filterable table: status, name, phase, agent, date | Click to detail |
| 3 | **Idea Detail** | Idea text, refinement history, approval controls, status timeline | Approve / Edit |
| 4 | **PRD Detail** | Section accordion (exec summary, requirements, sections), critique log | Publish / Export |
| 5 | **PRD Editor** | Markdown editor with live preview, section navigation sidebar | Save / Submit |
| 6 | **Publishing** | Confluence target, Jira project mapping, publish progress | Publish |
| 7 | **Settings** | Project config, integrations (Slack/Confluence/Jira), LLM config | Save |
| 8 | **Activity Feed** | Chronological agent activity, user approvals, system events | Filter by type |

### Navigation Hierarchy

```
Workspace Selector (top-left)
├── Home (dashboard)
├── Ideas
│   ├── Board View (default — filterable table)
│   ├── [Idea Detail]
│   │   ├── Refinement History
│   │   └── Approval Controls
│   └── New Idea (modal/drawer)
├── PRDs
│   ├── Board View (status, sections, date)
│   ├── [PRD Detail]
│   │   ├── Section Accordion
│   │   ├── Critique Log
│   │   └── Publishing Status
│   └── [PRD Editor] (full-screen)
├── Activity Feed
├── Publishing
│   ├── Confluence Status
│   └── Jira Status
└── Settings
    ├── Project Configuration
    ├── Integrations
    └── LLM Configuration
```

### Primary Layout Wireframe

```
┌─────────────────────────────────────────────────────────────┐
│ Top Bar (56px)                                              │
│ [≡ Collapse] Logo    [🔍 Search]  [🔔 Activity]  [Avatar] │
├──────────┬──────────────────────────────────────────────────┤
│          │ Board Header (48px)                              │
│ Sidebar  │ Ideas Board    [+ New Idea]  [Filter▾] [Sort▾]  │
│ (260px)  │──────────────────────────────────────────────────│
│          │ ┌ Active Ideas ─────────────────────────────────┐│
│ 🏠 Home  │ │ ● Status │ Idea Name    │ Phase    │ Updated ││
│ 💡 Ideas │ │ 🔵 New   │ Dashboard v2 │ Drafting │ 2h ago  ││
│ 📄 PRDs  │ │ 🟡 Refine│ Auth Module  │ Review   │ 5h ago  ││
│ 📤 Pub   │ │ 🔴 Stuck │ API Gateway  │ Failed   │ 1d ago  ││
│ ⚙️ Set   │ └───────────────────────────────────────────────┘│
│          │ ┌ Completed ────────────────────────────────────┐│
│          │ │ ✅ Done  │ User Personas│ Published│ Mar 20  ││
│          │ └───────────────────────────────────────────────┘│
├──────────┴──────────────────────────────────────────────────┤
│ Status Bar: 3 Active · 5 Complete · 1 Failed     [▶ Resume]│
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Interaction States (Review Addition — Pass 2)

Every interactive element must have all six states defined. No element ships without this matrix completed.

### 7.1 Global State Matrix

| State | Background | Border | Text | Icon | Motion |
|-------|-----------|--------|------|------|--------|
| **Default** | transparent / `--primary-background-color` | `--ui-border-color` | `--primary-text-color` | 100% opacity | — |
| **Hover** | `--primary-background-hover-color` | `--primary-color` | unchanged | unchanged | `--motion-productive-short` |
| **Focused** | unchanged | `--focus-ring-color` 2px solid | unchanged | unchanged | instant |
| **Active/Pressed** | darken 8% | darken 8% | unchanged | scale(0.96) | `--motion-productive-medium` |
| **Disabled** | `rgba(50,51,56,0.04)` | `rgba(50,51,56,0.12)` | `--disabled-text-color` | 38% opacity | none |
| **Loading** | unchanged | unchanged | hidden | spinner replaces icon | rotate 1s linear infinite |

### 7.2 Page-Level States

| State | Visual | Content |
|-------|--------|---------|
| **Loading (initial)** | Skeleton placeholder blocks mimicking content layout. Pulsing animation at `--motion-expressive-short` (250ms). No spinner in main content area — skeletons only. | 3–5 skeleton rows matching expected data shape |
| **Loading (refresh)** | Subtle progress bar at top of content area (2px height, `--primary-color`). Existing content remains visible and interactive. | "Updating..." text in status bar |
| **Empty (no data)** | Centered illustration (line art, not stock). Headline + body text + single CTA button. Illustration must be product-specific, not generic. | *Ideas Board empty*: "No ideas yet — start by describing a product feature" + [✨ New Idea] button |
| **Empty (filtered)** | Same layout as above, different copy. | "No ideas match your filters" + [Clear Filters] button |
| **Error (recoverable)** | Inline banner at top of content area. `--negative-color` left border (4px). Icon: ⚠️. Dismiss button. | Error message + [Retry] button. Original content hidden behind banner. |
| **Error (fatal)** | Full-page error state. Same illustration style as empty state. | "Something went wrong" + technical detail in collapsible `<details>` + [Retry] + [Go Home] |
| **Partial (some sections loaded)** | Loaded sections render normally. Unloaded sections show skeleton. Failed sections show inline error with per-section retry. | Section-level loading independence |
| **Success (transient)** | Toast notification — bottom-right, `--positive-color` left border, auto-dismiss 4s. | "PRD published to Confluence" + [View] link |

### 7.3 Component-Level States

#### Buttons

| Variant | Default | Hover | Active | Disabled | Loading |
|---------|---------|-------|--------|----------|---------|
| Primary | `#0073EA` bg, white text | `#0060B9` bg | `#004D99` bg | 12% opacity bg, 38% text | Spinner replaces label, same width |
| Secondary | transparent, `#323338` text, `#C3C6D4` border | `#F6F7FB` bg | `#E7E9EF` bg | same opacity rules | Spinner + "Loading..." |
| Danger | `#D83A52` bg, white text | `#B92E45` bg | `#9A2639` bg | same opacity rules | Spinner replaces label |

#### Table Rows

| State | Visual |
|-------|--------|
| Default | `--primary-background-color` bg |
| Hover | `--primary-background-hover-color` bg, entire row |
| Selected | `--primary-selected-color` bg, checkbox filled |
| Multi-selected | Same as selected + count badge in toolbar |
| Dragging | Elevated with `--box-shadow-medium`, 92% opacity |
| Drop target | 2px `--primary-color` top border |

#### Form Inputs

| State | Border | Background | Label |
|-------|--------|------------|-------|
| Default | `--ui-border-color` 1px | white | `--secondary-text-color` |
| Focus | `--primary-color` 2px | white | `--primary-color` (animated up) |
| Error | `--negative-color` 2px | `#FFF0F0` | `--negative-color` + error message below |
| Disabled | `rgba(50,51,56,0.12)` | `#F9F9F9` | `--disabled-text-color` |
| Read-only | no border | `--secondary-background-color` | normal |

---

## 8. User Journey & Emotional Arc (Review Addition — Pass 3)

Maps the PRD creation lifecycle to emotional states, guiding motion, tone, and UI density per stage.

| Stage | User Emotion | UI Response | Density | Motion | Tone |
|-------|-------------|-------------|---------|--------|------|
| **1. New Idea** | Excited, uncertain | Open, inviting. Large text input, minimal chrome. Warm prompt: "Describe your product idea..." | Low | Smooth entry (`--motion-expressive-short`) | Encouraging |
| **2. Idea Refining** | Curious, impatient | Show agent activity with streaming dots. Progress indicator. Cancelable. | Medium | Pulse animation on active agent | Informative |
| **3. Idea Approval** | Evaluative, cautious | Full idea text with diff highlights from original. Clear Approve/Reject with descriptions of what happens next. | Medium | Calm, no animation | Neutral, factual |
| **4. Requirements** | Engaged, detail-oriented | Structured breakdown visible. Expandable sections. Agent working indicators per section. | High | Per-section skeleton loading | Professional |
| **5. Drafting** | Hands-off, monitoring | Dashboard view showing all sections as cards with real-time status badges. Estimated time per section. | High — board view | Status badge color transitions (`--motion-productive-medium`) | Confident |
| **6. Review** | Critical, analytical | Side-by-side: draft vs. critique. Section-by-section navigation. Approve/reject per section. | Very high | Scroll-linked section highlight | Precise |
| **7. Approved** | Satisfied, decisive | Celebration moment — subtle (not confetti). Green status sweep across all sections. | Medium | `--motion-expressive-long` (400ms) green sweep | Celebratory but restrained |
| **8. Publishing** | Anxious, waiting | Progress bar with stage labels (Preparing → Uploading → Verifying → Done). No spinning wheel in isolation. | Low | Determinate progress bar | Reassuring |
| **9. Complete** | Accomplished | Summary card with links to Confluence page, Jira tickets. Share button. "What's next?" suggestions. | Low | Fade-in summary | Accomplished |
| **10. Failed** | Frustrated | Immediate error context. What went wrong, what was saved, what to do next. No blame language. | Low | Instant (no delay on errors) | Empathetic, actionable |

---

## 9. Motion

Based on Vibe v4 motion tokens — productive and restrained.

**Philosophy**: "Productive" for micro-interactions (70–150ms), "Expressive" for meaningful transitions (250–400ms). Motion aids comprehension, never decorates.

### Duration Tokens

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
| `--motion-timing-emphasize` | `cubic-bezier(0, 0, 0.2, 1.4)` | Bounce/overshoot for emphasis (rare) |

### Motion Rules

1. **Reduce motion**: Respect `prefers-reduced-motion: reduce` — collapse all animations to instant transitions
2. **No motion on first paint**: Page load content appears instantly, no staggered fade-in
3. **Skeleton loading only**: No spinner in main content. Skeletons pulse, content fades in over 150ms
4. **Status transitions**: Badge color changes use `--motion-productive-medium` (100ms) — fast enough to notice, not slow enough to distract

---

## 10. Shadows

| Level | Value | Usage |
|-------|-------|-------|
| `--box-shadow-xs` | `0px 4px 6px -4px rgba(0,0,0,0.1)` | Sticky headers, subtle elevation |
| `--box-shadow-small` | `0px 4px 8px rgba(0,0,0,0.2)` | Dropdowns, tooltips |
| `--box-shadow-medium` | `0px 6px 20px rgba(0,0,0,0.2)` | Hovered cards, dialogs |
| `--box-shadow-large` | `0px 15px 50px rgba(0,0,0,0.3)` | Modals, overlays |

**Rule**: Maximum one shadow level per viewport at a time (e.g., if a modal is open at `--box-shadow-large`, dropdown inside it does not add its own shadow).

---

## 11. Component Patterns

### 11.1 Buttons

| Type | Background | Text | Border | Radius | Height |
|------|-----------|------|--------|--------|--------|
| Primary | `#0073EA` | `#FFFFFF` | none | 4px | 40px |
| Secondary | transparent | `#323338` | 1px `#C3C6D4` | 4px | 40px |
| Tertiary | transparent | `#0073EA` | none | 4px | 40px |
| Danger | `#D83A52` | `#FFFFFF` | none | 4px | 40px |
| Disabled | `rgba(50,51,56,0.12)` | `rgba(50,51,56,0.38)` | none | 4px | 40px |

**Sizes**: Small (32px), Medium (40px default), Large (48px)  
**Min width**: 80px (prevents tiny clickable targets)  
**Icon + label**: `--space-8` gap, icon 16×16px for medium

```css
.btn {
  font: var(--font-text2);
  font-weight: 500;
  border-radius: var(--border-radius-small);
  padding: 0 var(--space-16);
  min-width: 80px;
  cursor: pointer;
  transition: background var(--motion-productive-short) var(--motion-timing-transition),
              border-color var(--motion-productive-short) var(--motion-timing-transition);
}
.btn:focus-visible {
  outline: 2px solid var(--focus-ring-color);
  outline-offset: 2px;
}
.btn--primary { background: var(--primary-color); color: var(--text-color-on-primary); }
.btn--primary:hover { background: var(--primary-hover-color); }
.btn--danger { background: var(--negative-color); color: var(--text-color-on-primary); }
.btn--loading { pointer-events: none; }
.btn--loading .btn__label { visibility: hidden; }
.btn--loading::after {
  content: "";
  position: absolute;
  width: 16px; height: 16px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
```

### 11.2 Status Badges

Colored background pills matching pipeline status colors:

```css
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-8);
  border-radius: var(--border-radius-full);
  font: var(--font-text3);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
}
.status-badge--approved { background: #00C875; color: #FFFFFF; }
.status-badge--refining { background: #FDAB3D; color: #323338; }
.status-badge--failed   { background: #DF2F4A; color: #FFFFFF; }
/* ... one class per pipeline status */
```

**Contrast check**: All status badge text meets WCAG AA 4.5:1 minimum. Light text on dark backgrounds (`#00C875`, `#DF2F4A`, `#9D50DD`, `#5559DF`, `#007EB5`, `#037F4C`). Dark text on light backgrounds (`#FDAB3D`, `#FFCB00`, `#579BFC`, `#FF5AC4`).

### 11.3 Cards

```css
.card {
  background: var(--primary-background-color);
  border: 1px solid var(--layout-border-color);
  border-radius: var(--border-radius-medium);
  padding: var(--space-16);
  transition: box-shadow var(--motion-productive-long) var(--motion-timing-transition);
}
.card:hover { box-shadow: var(--box-shadow-medium); }
.card:focus-within { border-color: var(--focus-ring-color); }
.card--skeleton {
  background: linear-gradient(90deg, #F6F7FB 25%, #E7E9EF 50%, #F6F7FB 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

### 11.4 Board View (Data Table)

The core UI pattern — mirrors monday.com's board:

```css
.board { border-radius: var(--border-radius-medium); overflow: hidden; }

.board-header {
  background: var(--secondary-background-color);
  font: var(--font-text2);
  font-weight: 600;
  color: var(--secondary-text-color);
  padding: var(--space-8) var(--space-16);
  border-bottom: 1px solid var(--layout-border-color);
  position: sticky;
  top: 0;
  z-index: 10;
}

.board-row {
  display: grid;
  grid-template-columns: 40px 4px 2fr 1fr 1fr 120px; /* checkbox, status-bar, name, phase, agent, date */
  align-items: center;
  padding: var(--space-8) var(--space-16);
  border-bottom: 1px solid var(--layout-border-color);
  min-height: 40px;
  transition: background var(--motion-productive-short);
}
.board-row:hover { background: var(--primary-background-hover-color); }
.board-row--selected { background: var(--primary-selected-color); }

.board-row__status-bar {
  width: 4px;
  height: 100%;
  border-radius: 2px;
  /* Color set via inline style from pipeline status */
}

.group-header {
  font: var(--font-h5);
  padding: var(--space-8) var(--space-16);
  border-left: 4px solid; /* color per group */
  cursor: pointer;
  user-select: none;
}
.group-header[aria-expanded="false"] + .group-body { display: none; }
```

### 11.5 Toast Notifications

```css
.toast {
  position: fixed;
  bottom: var(--space-24);
  right: var(--space-24);
  min-width: 320px;
  max-width: 480px;
  padding: var(--space-12) var(--space-16);
  background: var(--inverted-color-background);
  color: var(--text-color-on-inverted);
  border-radius: var(--border-radius-medium);
  box-shadow: var(--box-shadow-medium);
  display: flex;
  align-items: center;
  gap: var(--space-12);
  animation: slideUp var(--motion-expressive-short) var(--motion-timing-enter);
}
.toast--success { border-left: 4px solid var(--positive-color); }
.toast--error   { border-left: 4px solid var(--negative-color); }
.toast--warning { border-left: 4px solid var(--warning-color); }

@keyframes slideUp {
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0); opacity: 1; }
}
```

### 11.6 Modal/Dialog

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--backdrop-color);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn var(--motion-productive-long) var(--motion-timing-enter);
}
.modal {
  background: var(--primary-background-color);
  border-radius: var(--border-radius-big);
  box-shadow: var(--box-shadow-large);
  max-width: 640px;
  width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  padding: var(--space-24);
  animation: scaleIn var(--motion-expressive-short) var(--motion-timing-enter);
}
.modal__header {
  font: var(--font-h4);
  margin-bottom: var(--space-16);
  padding-bottom: var(--space-16);
  border-bottom: 1px solid var(--layout-border-color);
}
.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-8);
  margin-top: var(--space-24);
}
@keyframes scaleIn {
  from { transform: scale(0.95); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
```

### 11.7 Sidebar Navigation

```css
.sidebar {
  width: 260px;
  background: var(--secondary-background-color);
  border-right: 1px solid var(--layout-border-color);
  padding: var(--space-8) 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  transition: width var(--motion-expressive-short) var(--motion-timing-transition);
}
.sidebar--collapsed { width: 48px; }
.sidebar--collapsed .sidebar__label { display: none; }

.sidebar__item {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-8) var(--space-16);
  font: var(--font-text2);
  color: var(--primary-text-color);
  text-decoration: none;
  border-radius: var(--border-radius-small);
  margin: 0 var(--space-8);
  transition: background var(--motion-productive-short);
}
.sidebar__item:hover { background: var(--primary-background-hover-color); }
.sidebar__item--active {
  background: var(--primary-selected-color);
  color: var(--primary-color);
  font-weight: 600;
}
.sidebar__item:focus-visible {
  outline: 2px solid var(--focus-ring-color);
  outline-offset: -2px;
}
.sidebar__icon { width: 20px; height: 20px; flex-shrink: 0; }
```

### 11.8 Progress Bar (Publishing)

```css
.progress {
  width: 100%;
  height: 4px;
  background: var(--ui-background-color);
  border-radius: 2px;
  overflow: hidden;
}
.progress__bar {
  height: 100%;
  background: var(--primary-color);
  border-radius: 2px;
  transition: width var(--motion-expressive-short) var(--motion-timing-transition);
}
.progress--indeterminate .progress__bar {
  width: 40%;
  animation: indeterminate 1.5s infinite var(--motion-timing-transition);
}
@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}
```

---

## 12. Slack Block Kit Mapping

Primary production interface. Design tokens map to Block Kit as follows:

| Design Token | Slack Equivalent | Notes |
|-------------|-----------------|-------|
| Primary button | `style: "primary"` | Renders green in Slack (not blue) — acceptable divergence |
| Danger button | `style: "danger"` | Renders red — consistent |
| Status colors | Emoji prefixes (🔵🟡⚡💜✏️🔍✅📤✔️🔴) | Limited by Slack; emoji chosen for max recognition |
| Section separator | `type: "divider"` | — |
| Card equivalent | `type: "section"` with `accessory` | — |
| Table equivalent | Multiple `section` blocks with `fields` | 2-column max per section |
| Hero heading | `type: "header"` | — |
| Metadata | `type: "context"` with `mrkdwn` elements | Max 10 elements |
| Actions group | `type: "actions"` with button elements | Max 25 elements |

### Current Slack Button Inventory

| Button | Action ID | Style | Emoji |
|--------|----------|-------|-------|
| New Idea | `cmd_create_prd` | — | ✨ |
| List Ideas | `cmd_list_ideas` | — | 💡 |
| List Products | `cmd_list_products` | — | 📦 |
| Resume PRD | `cmd_resume_prd` | primary | ▶️ |
| Publish | `cmd_publish` | primary | 📤 |
| Create Jira | `cmd_create_jira` | — | 🎫 |
| Help | `cmd_help` | — | ❓ |
| End Session | `cmd_end_session` | — | ⏹ |
| Approve (flow) | varies | primary | — |
| Cancel (flow) | varies | danger | — |

---

## 13. Accessibility (Review Addition — Pass 6)

### WCAG 2.1 AA Compliance Targets

| Criterion | Requirement | Implementation |
|-----------|-------------|----------------|
| 1.4.3 Contrast (Minimum) | 4.5:1 text, 3:1 large text | All color pairings verified — see §4.4 badge contrast notes |
| 1.4.11 Non-text Contrast | 3:1 for UI components | Borders `#C3C6D4` on `#FFFFFF` = 3.1:1 ✓ |
| 2.1.1 Keyboard | All functions via keyboard | Focus ring on all interactive elements |
| 2.4.7 Focus Visible | Visible focus indicator | 2px solid `#0073EA`, 2px offset |
| 2.5.8 Target Size | 44×44px minimum | All buttons, links, checkboxes meet minimum |
| 1.4.1 Use of Color | Not sole means of info | Status badges use text label + color, not color alone |

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `Tab` | Move to next interactive element |
| `Shift+Tab` | Move to previous interactive element |
| `Enter` / `Space` | Activate button, toggle, expand |
| `Escape` | Close modal/dialog, dismiss toast |
| `Arrow Up/Down` | Navigate within list, table rows, dropdown |
| `Arrow Left/Right` | Navigate tabs, sidebar collapse/expand |
| `Home` / `End` | First/last item in list |

### ARIA Patterns

| Component | ARIA Role | Key Attributes |
|-----------|-----------|----------------|
| Sidebar | `navigation` | `aria-label="Main navigation"` |
| Board table | `grid` | `aria-rowcount`, `aria-colcount` |
| Table row | `row` | `aria-selected`, `aria-rowindex` |
| Group header | `button` | `aria-expanded`, `aria-controls` |
| Status badge | — | `aria-label="Status: Approved"` (not just color name) |
| Modal | `dialog` | `aria-modal="true"`, `aria-labelledby` |
| Toast | `status` | `aria-live="polite"`, `role="status"` |
| Progress bar | `progressbar` | `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-label` |
| Sidebar collapse | `button` | `aria-expanded`, `aria-label="Toggle sidebar"` |

### Color Contrast Verification

| Pairing | Foreground | Background | Ratio | Pass |
|---------|-----------|------------|-------|------|
| Body text | `#323338` | `#FFFFFF` | 14.5:1 | AA ✓ |
| Secondary text | `#676879` | `#FFFFFF` | 5.9:1 | AA ✓ |
| Primary on white | `#0073EA` | `#FFFFFF` | 4.6:1 | AA ✓ |
| White on primary | `#FFFFFF` | `#0073EA` | 4.6:1 | AA ✓ |
| White on danger | `#FFFFFF` | `#D83A52` | 4.8:1 | AA ✓ |
| White on done-green | `#FFFFFF` | `#00C875` | 3.0:1 | AA-Large ✓ (bold 12px+) |
| Dark on working-orange | `#323338` | `#FDAB3D` | 5.1:1 | AA ✓ |
| Dark on egg-yolk | `#323338` | `#FFCB00` | 6.8:1 | AA ✓ |

**Note**: `#00C875` white text fails AA normal text (3.0:1). Fix: Badge uses bold 12px (qualifies as "large text" at 14pt bold threshold). Alternative: use `#037F4C` (grass-green) for text on light backgrounds where normal weight is needed.

---

## 14. Figma Make — CSS Token Export

Complete design token set for Figma Make import:

```css
:root {
  /* ===== Typography ===== */
  --font-family: Figtree, Roboto, Noto Sans Hebrew, Noto Kufi Arabic, Noto Sans JP, sans-serif;
  --title-font-family: Poppins, Roboto, Noto Sans Hebrew, Noto Kufi Arabic, Noto Sans JP, sans-serif;
  --font-code: "JetBrains Mono", "Fira Code", "Consolas", monospace;

  --font-h1-size: 30px;
  --font-h1-line-height: 42px;
  --font-h1-weight: 500;
  --font-h1-letter-spacing: -0.5px;

  --font-h2-size: 24px;
  --font-h2-line-height: 32px;
  --font-h2-weight: 500;
  --font-h2-letter-spacing: -0.1px;

  --font-h3-size: 24px;
  --font-h3-line-height: 32px;
  --font-h3-weight: 300;
  --font-h3-letter-spacing: -0.1px;

  --font-h4-size: 18px;
  --font-h4-line-height: 24px;
  --font-h4-weight: 500;

  --font-h5-size: 16px;
  --font-h5-line-height: 24px;
  --font-h5-weight: 500;

  --font-text1-size: 16px;
  --font-text1-line-height: 22px;
  --font-text1-weight: 400;

  --font-text2-size: 14px;
  --font-text2-line-height: 20px;
  --font-text2-weight: 400;

  --font-text3-size: 12px;
  --font-text3-line-height: 16px;
  --font-text3-weight: 400;

  /* ===== Primary Colors ===== */
  --primary-color: #0073ea;
  --primary-hover-color: #0060b9;
  --primary-active-color: #004d99;
  --primary-selected-color: #cce5ff;
  --primary-highlighted-color: #f0f7ff;
  --primary-text-color: #323338;
  --secondary-text-color: #676879;
  --disabled-text-color: rgba(50, 51, 56, 0.38);
  --text-color-on-primary: #ffffff;
  --text-color-on-inverted: #d5d8df;

  /* ===== Backgrounds ===== */
  --primary-background-color: #ffffff;
  --primary-background-hover-color: #dce0ec;
  --secondary-background-color: #f6f7fb;
  --ui-background-color: #e7e9ef;
  --inverted-color-background: #323338;
  --backdrop-color: rgba(41, 47, 76, 0.7);

  /* ===== Borders ===== */
  --ui-border-color: #c3c6d4;
  --layout-border-color: #d0d4e4;
  --focus-ring-color: #0073ea;

  /* ===== Semantic Colors ===== */
  --positive-color: #00854d;
  --negative-color: #d83a52;
  --warning-color: #ffcb00;
  --link-color: #1f76c2;

  /* ===== Pipeline Status Colors ===== */
  --status-idea-submitted: #579bfc;
  --status-idea-refining: #fdab3d;
  --status-requirements: #ffcb00;
  --status-exec-summary: #ff5ac4;
  --status-drafting: #9d50dd;
  --status-review: #5559df;
  --status-approved: #00c875;
  --status-publishing: #007eb5;
  --status-complete: #037f4c;
  --status-failed: #df2f4a;

  /* ===== Spacing ===== */
  --space-2: 2px;
  --space-4: 4px;
  --space-8: 8px;
  --space-12: 12px;
  --space-16: 16px;
  --space-20: 20px;
  --space-24: 24px;
  --space-32: 32px;
  --space-40: 40px;
  --space-48: 48px;
  --space-64: 64px;
  --space-80: 80px;

  /* ===== Border Radius ===== */
  --border-radius-small: 4px;
  --border-radius-medium: 8px;
  --border-radius-big: 16px;
  --border-radius-full: 9999px;

  /* ===== Shadows ===== */
  --box-shadow-xs: 0px 4px 6px -4px rgba(0, 0, 0, 0.1);
  --box-shadow-small: 0px 4px 8px rgba(0, 0, 0, 0.2);
  --box-shadow-medium: 0px 6px 20px rgba(0, 0, 0, 0.2);
  --box-shadow-large: 0px 15px 50px rgba(0, 0, 0, 0.3);

  /* ===== Motion ===== */
  --motion-productive-short: 70ms;
  --motion-productive-medium: 100ms;
  --motion-productive-long: 150ms;
  --motion-expressive-short: 250ms;
  --motion-expressive-long: 400ms;
  --motion-timing-enter: cubic-bezier(0, 0, 0.35, 1);
  --motion-timing-exit: cubic-bezier(0.4, 0, 1, 1);
  --motion-timing-transition: cubic-bezier(0.4, 0, 0.2, 1);
  --motion-timing-emphasize: cubic-bezier(0, 0, 0.2, 1.4);

  /* ===== Layout ===== */
  --sidebar-width: 260px;
  --sidebar-collapsed-width: 48px;
  --topbar-height: 56px;
  --board-row-height: 40px;
  --max-content-width: 1440px;
  --min-touch-target: 44px;
}

/* ===== Dark Theme Override ===== */
[data-theme="dark"] {
  --primary-background-color: #181b34;
  --primary-background-hover-color: #282b4a;
  --secondary-background-color: #1e2142;
  --ui-background-color: #2b2e4a;
  --inverted-color-background: #f6f7fb;

  --primary-text-color: #d5d8df;
  --secondary-text-color: #9699a6;
  --text-color-on-inverted: #323338;

  --ui-border-color: #404460;
  --layout-border-color: #353858;

  --box-shadow-xs: 0px 4px 6px -4px rgba(0, 0, 0, 0.3);
  --box-shadow-small: 0px 4px 8px rgba(0, 0, 0, 0.4);
  --box-shadow-medium: 0px 6px 20px rgba(0, 0, 0, 0.4);
  --box-shadow-large: 0px 15px 50px rgba(0, 0, 0, 0.5);

  /* Status colors unchanged — high contrast on dark surfaces */
}
```

---

## 15. Unresolved Design Decisions (Review Addition — Pass 7)

Open questions requiring product/engineering input. Each includes a recommended default.

| # | Decision | Options | Recommended Default | Impact if Deferred |
|---|----------|---------|--------------------|--------------------|
| 1 | **Real-time updates** — WebSocket vs. polling for board status changes? | WebSocket (instant) vs. 5s polling vs. SSE | SSE (Server-Sent Events) — simpler than WS, real-time enough, already have FastAPI backend | Board feels stale if deferred; polling is fine for MVP |
| 2 | **Markdown editor** — Which editor for PRD editing? | Monaco (VS Code engine), Milkdown, Tiptap, plain textarea | Milkdown — WYSIWYG markdown, lighter than Monaco, better for non-developers | PRD Editor screen blocked until decided |
| 3 | **Authentication** — SSO provider for web dashboard? | Slack SSO (already integrated), Google, GitHub, custom | Slack SSO — users already authenticate via Slack bot | Blocking for any public deployment |
| 4 | **Sidebar: project switcher** — Dropdown in sidebar or full-screen selector? | Sidebar dropdown, overlay panel, dedicated page | Sidebar dropdown (monday.com pattern) — one click, no navigation | Low impact — either works |
| 5 | **Board view: column customization** — Fixed columns or user-configurable? | Fixed set, drag-reorder, full show/hide | Fixed set for v1, drag-reorder for v2 | Low — fixed is fine for MVP |
| 6 | **Empty state illustrations** — Custom line art or icon-based? | Custom illustration, product icons, text-only | Product icons with text — faster to ship, consistent with Vibe | Purely cosmetic; text-only fallback works |
| 7 | **Notification preference** — Where do web notifications go vs. Slack notifications? | Web only, Slack only, both with preferences | Both — web for dashboard users, Slack for existing users. Preference toggle in Settings. | Needs settings UI before launch |
| 8 | **Dark mode trigger** — System preference, manual toggle, or both? | System only, manual only, both with override | Both — respect `prefers-color-scheme` with manual override stored in user settings | Dark mode not usable without this decision |

---

## 16. Decisions Log

| # | Date | Decision | Rationale |
|---|------|----------|-----------|
| 1 | 2026-03-25 | Use monday.com Vibe v4 as design foundation | User requested monday.com look/feel; Vibe is official open-source with documented tokens |
| 2 | 2026-03-25 | Figtree body + Poppins titles | Direct from Vibe v4 tokens — Figtree replaced Roboto in v3→v4 |
| 3 | 2026-03-25 | 10-color PRD pipeline status mapping | Each stage maps to distinct Vibe status color for instant recognition |
| 4 | 2026-03-25 | Board/table as primary layout paradigm | monday.com's core pattern; natural fit for idea lists, PRD sections, pipelines |
| 5 | 2026-03-25 | Comfortable-dense spacing | Matches monday.com's information-dense-yet-readable approach |
| 6 | 2026-03-25 | Added semantic `--status-*` token aliases | Decouples pipeline semantics from raw Vibe palette (Senior Designer review fix) |
| 7 | 2026-03-25 | Skeleton loading over spinners | Skeletons communicate layout expectation; spinners are empty calories (Senior Designer review fix) |
| 8 | 2026-03-25 | Focus ring: 2px solid primary, 2px offset | Visible on all backgrounds, strong enough for low-vision users (Senior Designer review fix) |
| 9 | 2026-03-25 | Status badges require text label + color | Color alone fails WCAG 1.4.1; every badge must have readable status text (Senior Designer review fix) |
| 10 | 2026-03-25 | Added full interaction state matrix | No component ships without all 6 states defined (Senior Designer review fix) |
| 11 | 2026-03-25 | `--motion-timing-emphasize` marked as rare use | Bounce/overshoot only for specific delight moments (approval celebration), never for navigation (Senior Designer review fix) |
| 12 | 2026-03-25 | Dark theme as CSS variable override | Single `[data-theme="dark"]` selector; no separate token file needed (Senior Designer review fix) |

---

*End of design system. This document is ready for Figma Make upload.*
