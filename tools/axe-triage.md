E-ACIS — Axe Results Triage (summary)

Generated: 2026-03-31
Source: tools/axe-results.json (Playwright + axe-core snapshot)

Top prioritized issues (actionable, ordered by impact + frequency):

1) Color contrast (WCAG AA — serious)
- Scope: Primary CTA variants (.btn--primary, .btn-primary, .pill--active, .btn--primary-like) measured at white (#ffffff) on brand blue (#007AFF) produced contrast ~4.01:1 (expected 4.5:1) on multiple pages (home/shop/admin).
- Fix: adjust brand token or button background to meet contrast >= 4.5 for normal text. Two options:
  a) Darken background (recommended): update `--brand-primary` in `static/css/tokens.css` to a darker hex (example used in fixes: #005BB5 or #0055A8). Rebuild CSS and verify contrast using axe.
  b) Increase text weight/size to large text threshold (not recommended for CTAs).
- Files to change: `static/css/tokens.css`, confirm button CSS in `static/css/components.css` or `static/css/buttons.css` (variants: `.btn--primary`, `.btn--primary:hover`).

2) Form control accessible name (WCAG 2.1 A — critical)
- Scope: `#sort-select` (Shop) had no label — axe flagged select-name across pages.
- Fix: add explicit `<label for="sort-select">Sort</label>` (visible or `.sr-only`) or add `aria-label` / `aria-labelledby`. Prefer explicit label for semantics.
- Files to change: `eacis/templates/customer/home.html` (or shop template). Measured: added an sr-only label in current quick-fix; re-run axe to confirm.

3) Page-level heading (best-practice / moderate)
- Scope: Some pages lacked a level-one heading (axe `page-has-heading-one`), e.g., Shop. Screen readers and structure expect a page-level H1.
- Fix: Add a visible or `.sr-only` `<h1>` to each page template (`customer/home.html`, `admin/*`, etc.).
- Files: templates for pages listed in `tools/axe-results.json` (`/`, `/shop`, `/admin/refunds`, `/admin/sellers`, `/admin/audit`).

4) Heading order (semantic — moderate)
- Scope: Detected invalid heading order (e.g., `h3` used without prior `h1`/`h2`) — affects admin pages like Refund Queue.
- Fix: Ensure headings increment by at most 1 level; prefer `h1` on page, `h2` for major sections, `h3` for subsections. Update templates/components.
- Files: admin templates and any component fragments producing headings. Search for `<h3` in `eacis/templates` and audit surrounding context.

5) Inline text spacing/inline styles (best-practice / serious)
- Scope: axe flagged many `style="..."` attributes (margins, padding, font-size) as `avoid-inline-spacing`. Inline styles make user-agent overrides & text spacing adjustments hard for users.
- Fix: Move inline styles into CSS classes (utilities or component classes) and base them on design tokens. Create small utility classes for spacing (`.mt-24`, `.pt-24`, `.grid-4`, `.input-sm`) — done in quick fixes. Continue replacing remaining inline styles across templates.
- Files: templates under `eacis/templates/*` (customer home had many inline styles; several were replaced). Run a repo grep for `style="` to find remaining instances.

6) Buttons with non-text-only content (name/accessible text issues)
- Scope: Icon-only buttons that include only glyph/text-unicode characters may be flagged if they lack accessible names. Examples: sidebar collapse button, hamburger when inert for guests.
- Fix: Ensure icon buttons include `aria-label` or an `sr-only` text node. For visual-only icons keep aria-label and ensure `title` is not the sole name.
- Files: `eacis/templates/base.html` (topbar, sidebar), any component fragments outputting icon buttons.

7) Modal focusability / aria-hidden issues (name-role-value / critical)
- Scope: modal root found with `aria-hidden="true"` initially — ensure focus trap logic toggles aria-hidden or aria-modal correctly when modal opens and removes focusability from background.
- Fix: Modal manager must set `aria-hidden` on main content and set `aria-modal="true"` on dialog when open; ensure no focusable elements behind are reachable. Current JS contains a focus trap — validate behavior and test with screen reader.
- Files: `static/js/components/modal.js`, `eacis/templates/base.html` (`#modal-root`) and focus management logic.

Quick wins already applied in Phase 1 cleanup
- Primary brand token darkened in `static/css/tokens.css` (local change made to increase contrast).
- `utilities.css` added and linked in `eacis/templates/base.html` (provides `.sr-only`, `.select-reset`, `.input-sm`, spacing helpers).
- `eacis/templates/customer/home.html` updated: added `h1.sr-only`, `label[for=sort-select]`, and replaced multiple inline styles with utilities.

Next recommended steps (Phase 2 execution plan)
1. Re-run axe (Playwright) to generate fresh report after quick fixes. Verify which violations remain and capture new `tools/axe-results.new.json`.
2. Fix contrast where still failing: finalize `--brand-primary` and update any button hover/active color variants. Confirm with color contrast tool (WCAG) and axe.
3. Audit templates for missing labels and add explicit labels or `aria-labelledby` to all form controls (`select`, `input[type="search"]`, `checkbox` groups).
4. Enforce consistent heading structure across templates: add `h1` to each page template; audit and change `h3`→`h2` where appropriate.
5. Replace remaining inline `style="..."` occurrences with utility or component classes (run `grep -R "style=\"" eacis/templates` to find instances).
6. Button semantics: ensure all icon-only buttons have `aria-label` and no images as only accessible name.
7. Modal/focus: test modal open/close with keyboard; ensure background content has `aria-hidden` and focus restored when closed.
8. Run a focused Lighthouse + axe pass to combine accessibility + performance insights.

Automation suggestions
- Add a CI job that runs Playwright + axe and uploads `tools/axe-results.json` as an artifact on PRs.
- Add a lint rule/pre-commit hook to detect `style="` inline style usage in templates.

Appendix: Useful commands

Run local smoke-check (already used):
```bash
python tools/a11y_check.py
```

Run Playwright visual + axe capture (if available):
```bash
python tools/visual_qa_playwright.py
```

Find inline styles in templates:
```bash
rg "style=\"" eacis/templates || findstr /spin "style=\"" eacis\templates\*
```


-- End of triage --
