# UX + Validation Overhaul Master Plan

This document prepares a full-system UX overhaul and robust validation program for E-ACIS.
It is designed for phased execution with clear quality gates.

## 1) Overhaul Objectives

1. Make the whole product experience consistent, predictable, and role-appropriate.
2. Enforce robust validation at UI, API, and database layers.
3. Eliminate fragmented behavior across customer/seller/admin flows.
4. Reduce user error and support burden with clear feedback and guardrails.
5. Produce measurable quality outcomes (task success, fewer invalid submissions, fewer role-access defects).

## 2) UX System Foundations (Global)

### 2.1 Design Language Rules

1. Single source of truth for spacing, type scale, colors, border radius, and elevation.
2. Use one semantic button taxonomy only:
	- Primary: critical forward actions.
	- Secondary: non-destructive alternatives.
	- Ghost: low-emphasis navigation/support actions.
	- Danger: destructive actions only.
3. Normalize form density and control heights per viewport.
4. Standardize badges/status chips across all portals.
5. Ensure all tables, cards, and filters use common interaction states (hover, focus, disabled, loading).

### 2.2 Interaction Contracts

1. All state-changing actions show pending state.
2. All async actions show success/failure feedback.
3. Every form uses inline field errors + top-level summary for non-field errors.
4. Empty states are instructive (what happened + what to do next).
5. Confirmation required for destructive actions.

### 2.3 Accessibility Baseline

1. Keyboard navigable controls and dialog traps.
2. Visible focus style on all interactive elements.
3. Label + hint + error association for form fields.
4. Sufficient contrast and non-color-only status cues.
5. ARIA-live for dynamic confirmation/errors where relevant.

## 3) Information Architecture Consistency

### 3.1 Customer

Core loop: Discover -> Product detail -> Cart -> Checkout -> Orders -> Returns -> Invoices.

Consistency rules:
1. Primary CTA remains context stable (example: Add to Cart, Proceed to Checkout, Place Order).
2. Cart summary should match checkout summary calculations exactly.
3. Returns must clearly show status progression and refund amount provenance.
4. Invoice access from both order detail and invoice list.

### 3.2 Seller

Core loop: Dashboard -> Orders/Returns -> Inquiries -> CRM -> Vouchers -> Reports.

Consistency rules:
1. Every KPI must map to real DB-backed definitions.
2. Filters/search semantics must be shared across seller list pages.
3. Refund actions must always show the computed amount before confirmation.
4. Export actions must be present and aligned for analytics/reporting pages.

### 3.3 Admin

Core loop: Oversight -> Verification -> Audit -> Reports.

Consistency rules:
1. Admin pages strictly role-restricted.
2. Sensitive actions auditable and confirmable.
3. Reports and exports use consistent metric definitions.

## 4) Robust Validation Architecture

## 4.1 Validation Layers

1. Client-side validation:
	- Immediate feedback for format/range/required fields.
	- Never treated as security control.
2. Server-side validation:
	- Canonical enforcement for all state-changing operations.
	- Returns explicit field-level and action-level errors.
3. Database constraints:
	- Unique keys, foreign keys, non-null where required.
	- Enum/domain enforcement aligned with business states.

### 4.2 Validation Standards by Data Domain

1. Identity:
	- first_name/middle_name/last_name/suffix character and length checks.
2. Address:
	- address_line1/address_line2/barangay/city_municipality/province/region/postal_code normalized.
	- postal suggestion + manual override validation.
3. Contact:
	- phone format validation and normalization.
4. Commerce:
	- qty > 0, stock bounds, installment eligibility checks.
5. Finance:
	- voucher constraints, loyalty bounds, refund amount non-negative and traceable.
6. Security:
	- password policy, rate limiting, lockout consistency, CSRF on mutating forms.

## 5) Route-by-Route Validation Matrix (Minimum)

### 5.1 Auth + Profile

1. /auth/register (customer/seller):
	- normalized name/address required set
	- postal and phone format
	- duplicate email handling
2. /auth/login:
	- lockout/rate limit consistency
3. /customer/profile and /seller/profile:
	- safe partial updates + normalized persistence

### 5.2 Shopping + Checkout

1. /shop, /products/<ref>:
	- product existence + active state
2. /cart:
	- add/update/remove with stock caps and valid quantity
	- voucher apply/remove validation with clear reason messages
3. /checkout:
	- address/contact required
	- payment method normalization
	- installment eligibility and plan validity
	- total consistency (subtotal, discount, loyalty, final)

### 5.3 Orders + Returns + Refunds

1. /customer/orders/<order_ref>:
	- ownership checks
2. /customer/returns:
	- ownership, duplicate request policy, reason/description required
	- deterministic refund_amount assignment
3. /seller/returns and /seller/returns/<rrt_ref>:
	- seller ownership check for order items
	- status transition guardrails
	- refund transaction creation with computed amount traceability

### 5.4 Invoices + Reports

1. /customer/invoices, /customer/invoices/<invoice_ref>:
	- ownership checks
2. /seller/invoices, /seller/invoices/<invoice_ref>:
	- seller ownership checks
3. report export endpoints:
	- role checks
	- successful response type and content

## 6) Implementation Phases (Execution Plan)

## Phase A: UX Foundation Alignment

1. Consolidate component variants and interaction states.
2. Normalize table/list/filter UX patterns.
3. Standardize feedback and empty states.

Exit criteria:
1. Shared UI patterns used across customer/seller/admin pages.
2. No conflicting primary actions per page.

## Phase B: Validation Consolidation

1. Centralize common validators (name/address/phone/postal/qty/password).
2. Refactor routes to use unified validators and error payload format.
3. Ensure form errors map back to specific fields in UI.

Exit criteria:
1. Reduced duplicated validation logic.
2. Predictable error behavior across forms.

## Phase C: End-to-End Data Consistency

1. Reconcile cart totals with checkout totals and order totals.
2. Validate invoice generation and role-restricted invoice access.
3. Validate return->refund trace with deterministic amounts.

Exit criteria:
1. Cross-page totals match.
2. Return/refund chain remains auditable and consistent.

## Phase D: Security Hardening

1. Introduce structured login rate limiting.
2. Enforce secure cookie flags in production config.
3. Expand object-level access tests.
4. Verify sensitive-log hygiene.

Exit criteria:
1. Authentication abuse controls active.
2. Role and object restrictions verified via automated checks.

## Phase E: QA + Regression Automation

1. Build regression scripts for customer/seller/admin critical paths.
2. Add negative tests for unauthorized and invalid actions.
3. Create release checklist and evidence bundle.

Exit criteria:
1. All critical paths pass in one run.
2. All acceptance criteria evidenced by test outputs.

## 7) QA Evidence Checklist

1. Customer E2E:
	- catalog -> product detail -> cart -> checkout -> order -> invoice -> return
2. Seller E2E:
	- order handling -> return decision -> refund transaction -> reports export
3. Admin E2E:
	- dashboard, seller review, audit, reports export
4. Security checks:
	- role restrictions and object-level access denials
	- CSRF and login abuse controls

## 8) Definition of Done (Overhaul)

1. UX consistency: no conflicting interaction patterns across portals.
2. Validation robustness: all mutating paths enforce server-side validation and clear UI error mapping.
3. Data integrity: order/invoice/return/refund/report data flows are consistent and traceable.
4. Security baseline: role/object restrictions and auth/session protections validated.
5. Operational readiness: regression scripts and release checklist available.

## 9) Immediate Next Sprint (Practical Sequence)

1. Build shared validation module and refactor high-risk routes first:
	- register, profile, cart, checkout, returns, seller refund update.
2. Unify form error rendering contract in customer/seller templates.
3. Add focused regression scripts for:
	- invoice ownership
	- seller return/refund ownership and amount integrity
	- report export role restrictions

## 10) Focus Lock Prompt (Use This Verbatim)

Paste the block below before each work session to keep execution strictly plan-driven:

```text
Continue implementation strictly following UX_VALIDATION_OVERHAUL_MASTER_PLAN.md only.

Execution rules:
1. Work phase-by-phase in order (A -> B -> C -> D -> E). Do not skip ahead.
2. For this turn, execute only: [PHASE + specific checklist items].
3. Do not introduce features outside the selected phase scope.
4. Before edits, list exact files you will modify and the mapped checklist item.
5. After edits, run validation/tests relevant to this phase.
6. End with this exact report format:
	- Completed checklist items
	- Files changed
	- Acceptance criteria status (pass/fail per item)
	- Gaps or blockers
	- Next phase-ready recommendation (yes/no)

If any request conflicts with this phase scope, explicitly mark it as out-of-scope and defer it.
```

