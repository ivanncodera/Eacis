# UI Implementation Plan for E-ACIS (2026-Aligned)

## 1. Decision: Is the 2026 Prompt Usable for This System?

Yes, with adaptation.

The system already has strong foundations:
- Design tokens and component primitives are centralized.
- Form, button, card, and table patterns are present.
- Sticky top navigation and portal sidebars are implemented.
- Existing interaction scripts already support submit loading and button feedback.

The prompt is usable as a standards reference if applied as:
- A design system upgrade path, not a full visual rewrite.
- A consistency and behavior contract across customer, seller, admin views.
- A phased rollout with measurable acceptance criteria.

## 2. Current Baseline (What Already Exists)

### 2.1 Design Language
- Token foundation exists in eacis/static/css/tokens.css.
- Core components exist in eacis/static/css/components.css.
- Layout and responsive scaffolding exist in eacis/static/css/layout.css and eacis/static/css/utilities.css.

### 2.2 Interaction and Motion
- Sticky topbar and role sidebars exist.
- Button ripple and submit-loading enhancement exist in eacis/static/js/ui/buttons.js.
- Toast/live region scaffold exists in base template.

### 2.3 Accessibility and Feedback
- Global feedback rendering exists in base layout.
- Form error classes and states exist in components CSS.
- Some pages already include breadcrumb patterns, but usage is inconsistent.

## 3. Gaps vs 2026 Prompt

### 3.1 Navigation and Exploration
- Breadcrumbs are not consistently present on deep pages.
- Search intent handling is present visually, but autocomplete quality varies by route.
- Guided exploration is not standardized for key journeys (discover to checkout, returns, analytics drill-down).

### 3.2 Layout Strategy (Bento and Modular)
- Card/grid systems exist, but bento hierarchy is inconsistent.
- Not all pages clearly enforce 1 to 2 primary focus cards per viewport.

### 3.3 Motion and Loading Feedback
- Submit loading exists, but not uniformly applied to all mutating forms.
- Skeleton loading is not standardized across table-heavy pages.

### 3.4 User-Centric Behavior
- CTA language consistency varies by page.
- Personalization signals exist by role, but intent-adaptive content blocks are limited.

### 3.5 Accessibility
- ARIA-live exists globally, but inline form error association and focus behavior are still uneven by template.

## 4. UI Standards Contract (System-Wide)

## 4.1 Grid Standards
- Use utility grid classes as default layout baseline.
- Use kpi-grid for KPI summaries and table-wrapper for data pages.
- Introduce bento section composition for dashboard and overview pages:
  - One primary card (decision/action card)
  - One secondary operational card (status/queue)
  - Remaining cards as tertiary context

## 4.2 Label and Input Standards
- Every input must have:
  - .form-label
  - required or optional indicator where applicable
  - inline error slot using .form-error
- All mutating forms must use data-enhance="submit-loading".
- Validation states must use is-error or is-success consistently.

## 4.3 Card Standards
- Base: .glass-card
- Interactive: .glass-card--interactive for clickable cards
- Metric: .glass-card--kpi for KPIs
- Hero/context: .glass-card--hero where narrative context is needed
- Empty states must include:
  - what happened
  - what to do next

## 4.4 Button and CTA Standards
- Primary action per panel must be singular and explicit.
- CTA text must be action-oriented:
  - Use Start, Continue, Review, Confirm, Export
  - Avoid generic Submit where context-specific verbs are possible
- Destructive actions must have confirmation prompts.

## 4.5 Accessibility Standards
- WCAG 2.2 AA color and contrast checks before page signoff.
- Keep visible focus ring on all interactive controls.
- Ensure inline errors are linked to relevant fields.
- Keep role-specific feedback discoverable through ARIA-live and visible inline messages.

## 5. Phase-by-Phase UI Rollout (Post Overhaul)

## Phase UI-1: Navigation and Breadcrumb Consistency
- Add breadcrumb header block to all deep hierarchy pages in customer, seller, admin portals.
- Standardize page header structure:
  - title
  - subtitle
  - context actions

Acceptance:
- Breadcrumbs present on all deep routes.
- Header anatomy consistent across portals.

## Phase UI-2: Bento and Focus Hierarchy
- Apply modular bento composition to dashboard-style pages.
- Enforce one primary decision card per screen.
- Ensure table pages keep one summary strip plus one actionable toolbar.

Acceptance:
- No dashboard page has more than two equal-priority hero cards.
- Scan path is clear in first screen view.

## Phase UI-3: Form and Validation UX Completion
- Apply submit-loading enhancement to all POST forms.
- Ensure top-level summary plus inline field errors where validation exists.
- Standardize helper text placement under controls.

Acceptance:
- All mutating forms show pending state.
- No form relies on flash-only errors for field validation.

## Phase UI-4: Motion and Loading System
- Introduce skeleton placeholders for high-latency table/card sections.
- Keep microinteractions subtle and state-driven.
- Avoid decorative animation where no state change exists.

Acceptance:
- Skeletons used on major data-loading views.
- No blocking spinner-only loading on primary list pages.

## Phase UI-5: Personalization and Intent Adaptation
- Add role-intent quick actions at top of each portal dashboard.
- Use recent activity and unresolved queues to prioritize cards.

Acceptance:
- Each role dashboard shows personalized, intent-prioritized actions.

## 6. QA and Verification Plan

For each portal page group:
- Visual consistency review:
  - grid
  - card hierarchy
  - CTA clarity
- Interaction review:
  - pending states
  - error handling
  - confirmations
- Accessibility review:
  - keyboard flow
  - focus visibility
  - screen reader labels and error association

Evidence artifacts:
- before and after screenshots per portal
- route checklist with pass or fail
- accessibility scan output plus manual notes

## 7. Recommended First Implementation Slice

Start with these high-impact pages:
1. customer/orders
2. customer/returns
3. seller/orders
4. seller/returns
5. admin/reports

Reason:
- They are workflow-dense, validation-heavy, and already partly standardized.
- Improvements here create immediate system-wide pattern templates.

## 8. Execution Status (In Progress)

### Completed: UI-1 Navigation and Breadcrumb Consistency
- Implemented breadcrumb + deep-page header contract (title, subtitle, context actions) on:
  - customer/orders
  - customer/returns
  - seller/orders
  - seller/returns
  - admin/reports
- Result: acceptance criteria met for the first implementation slice.

### Completed: UI-2 Focus Hierarchy (First Slice)
- Enforced summary strip plus actionable toolbar pattern on table-heavy pages in the first slice.
- Added KPI summary strips to:
  - customer/orders
  - customer/returns
  - seller/orders
- Existing KPI/toolbar layouts retained and aligned on:
  - seller/returns
  - admin/reports
- Result: first-screen scan path improved with clear summary-then-action structure.

### Completed: UI-3 Form and Validation UX Completion (First Slice)
- Filter toolbars on customer/orders, seller/orders, and seller/returns now use `.form-label`, helper text, `aria-describedby`, and `data-enhance="submit-loading"` with explicit `btn__label` on apply actions.
- Customer returns POST form: required-field markers use `abbr.required`, upload marked optional, primary CTA text is action-specific; removed static stepper and generic SLA copy in favor of counts-driven messaging.
- Seller return review modals: seller notes use `for`/`id`, helper text, optional indicator, and clearer submit labels; submit-loading prefers primary/secondary submit buttons (see `buttons.js`).
- Admin/reports: no mutating forms in this slice (export remains link-based).
- Public landing and shop discovery: category chips, hero spotlight, promos, trust metrics, and grids are driven from live product/user aggregates—not hardcoded product lists or fake ratings in grids (`productGrid.js` only shows ratings when data exists).

### Next: UI-4 Motion and Loading System (Next Slice)
- Skeleton placeholders for high-latency table/card sections on the expanded route set.

## 9. Strict Plan-Focus Prompt (Reuse)

Use this prompt to keep implementation strictly scoped:

"Use UI_IMPLEMENTATION_PLAN_2026.md as the only source of truth. Execute ONLY [PHASE NAME] for ONLY these routes/files: [LIST]. Do not do any out-of-scope refactors. Preserve existing design tokens/components. After changes, return: (1) checklist item completed, (2) files changed, (3) validation result, (4) remaining items in the same phase only. Stop when the selected phase scope is complete."

Shorter variant you can paste each session:

"Follow UI_IMPLEMENTATION_PLAN_2026.md only. Phase [N]. Files: [comma list]. No scope creep. Report checklist, diffs, and what is left in this phase."

## 10. End-User UI Journey Order (Rollout Sequence)

Implement and review UI in this flow so each step builds on the last (public → auth → role portals):

1. **Landing** (`/`, `/landing`) — first impression, catalog entry, seller CTA, data-driven highlights.
2. **Sign in** (`/auth/login`) — single entry for all roles; errors and loading per UI-3.
3. **Registration path** (`/auth/register`, role-specific registration) — before first protected action.
4. **Shop / discovery** (`/shop`, `/customer/home`) — browse and filter; aligns with landing category links.
5. **Customer account** (cart → checkout → orders → returns) — transactional depth.
6. **Seller portal** (dashboard → orders → returns → inventory, etc.) — operations.
7. **Admin** (dashboard → reports → settings) — oversight.

Within each phase (UI-1…UI-5), apply the same journey order when choosing which screens to touch first, so navigation, forms, and loading behavior stay consistent as users move down the funnel.
