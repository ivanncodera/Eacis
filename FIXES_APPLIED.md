# E-ACIS Demo Fixes & Security Hardening Report

**Prepared For:** E-ACIS Demonstration  
**Baseline Tests:** 23 Passing  
**Current Test Suite:** 30 Passing (23 baseline + 7 demo regression tests)  
**Rehearsal Simulation:** 44/44 Click-Path Steps Verified (0 HTTP 500s, 0 Redirect Loops)  
**Database Migration Status:** Unified at head `20261030_merge_all_heads` (0 schema changes)

---

## 1. Executive Summary

Ahead of the live demonstration, the E-ACIS platform was subjected to end-to-end security and functional remediation based on findings identified in `audit/REPORT.md`. All Critical (P0) and High-Priority (P1) business logic, multi-tenant isolation, financial integrity, and UI issues have been resolved, thoroughly tested, and verified against regression suites.

---

## 2. Master Table of Fixes Applied

| Finding ID | Priority | Category | Problem Summary | Remediation Details | Primary Files & Lines | Status |
| :--- | :---: | :--- | :--- | :--- | :--- | :---: |
| **`LOGIC-01`** | **P0** | Business Logic | Missing `finalize_seller_refund` function header caused 500 `NameError` on seller refunds. | Restored header `def finalize_seller_refund(seller, rrt_ref):` and exposed on `app` instance. | `eacis/app.py:1598`, `5917` | **FIXED** |
| **`LOGIC-02`** | **P0** | Financial Integrity | Installment refunds paid 100% of order total even when 0 was paid; failed to cancel plan. | Capped refund to amount actually paid (`downpayment + sum(paid_schedules)`), set plan status to `cancelled`, and cancelled pending schedules. | `eacis/app.py:470-484`, `return_service.py:365-373, 441-454` | **FIXED** |
| **`LOGIC-08`** | **P0** | Loyalty Engine | Unearned loyalty points awarded on installment checkout and clawed back on refund. | Points awarded only when `payment_method == 'full_pay'`. Refund point deduction checks `LoyaltyTransaction` before deducting. | `eacis/app.py:3437`, `return_service.py:455-465` | **FIXED** |
| **`LOGIC-04`** | **P0** | State Machine | Sellers could jump order status illegally (e.g. `cancelled` -> `delivered`). | Strict transition dictionary enforced: `paid -> packed -> shipped -> delivered`. Disallowed jumps rejected with flash error. | `eacis/app.py:5744-5760` | **FIXED** |
| **`LOGIC-05`** | **P0** | Installment / KYC | Seller KYC approval prematurely marked orders and invoices as `paid`. | KYC approval recorded in order audit notes (`kyc approved by seller`) without marking order or invoice as paid before payments exist. | `eacis/app.py:6410-6435` | **FIXED** |
| **`LOGIC-03`** | **P0** | Multi-Seller / Payouts | Multi-seller orders blocked fulfillment and seller payouts calculated on total order. | Allowed any seller to advance fulfillment; computed `available_balance`, `pending_clearance`, and payout tables strictly from seller's `OrderItem`s. | `eacis/app.py:6970-6984, 7018-7019`, `seller/payouts.html:40` | **FIXED** |
| **`SEC-02`** | **P0** | Information Disclosure | Evidence uploads on returns accessible publicly without authentication. | Added `@app.route('/uploads/returns/<path:filename>')` requiring login and restricted to customer, seller on order, or admin. | `eacis/app.py:734-754` | **FIXED** |
| **`SEC-01`** | **P0** | IDOR / Multi-Tenant | Cross-tenant permit downloads and inquiry ticket hijacking across sellers. | Added strict tenant ownership check: permits restricted to owning seller/customer; tickets restricted to `assigned_to == current_user.id` (403). | `eacis/app.py:680-732, 6582-6584` | **FIXED** |
| **`UI-01`** | **P0** | Broken Endpoints | Saved addresses page posted to non-existent blueprint endpoints (`save_address`, etc.). | Updated form actions in `customer/addresses.html` to post directly to active `customer_addresses` endpoints. | `eacis/templates/customer/addresses.html:56, 128` | **FIXED** |
| **`SEC-06`** | **P0** | CSRF Vulnerability | Trusted device revocation forms lacked CSRF tokens. | Added hidden `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` to revocation forms in customer and admin templates. | `customer/trusted_devices.html:43`, `admin/trusted_devices.html:52` | **FIXED** |
| **`UI-02`** | **P0** | Template Variable Mismatch | Admin dashboard crashed/omitted OTP metrics due to missing keys in `stats`. | Added `otp_verify_rate_24h` and `otp_sent_24h` calculations matching template keys in `admin_dashboard`. | `eacis/app.py:7210-7225` | **FIXED** |
| **`LOGIC-06`** | **P0** | Cart Integrity | Partial cart checkout wiped all unselected items from customer's cart. | Updated `checkout()` to remove only purchased items from `cart.items`, keeping unselected items intact. | `eacis/app.py:3415-3425` | **FIXED** |
| **`LOGIC-07`** | **P0** | Voucher Accounting | `VchSvc.record_usage()` was never called upon order checkout. | Added explicit call to `VchSvc.record_usage(voucher.id, current_user.id, order.id, discount)` upon checkout completion. | `eacis/app.py:3428-3435` | **FIXED** |
| **`LOGIC-09`** | **P0** | Financial Analytics | Cancelled and refunded orders artificially inflated seller and admin revenue metrics. | Filtered sales and revenue calculations in `seller_analytics()` and `admin_reports()` to `status.in_(['paid', 'packed', 'shipped', 'delivered'])`. | `eacis/app.py:6012, 8155` | **FIXED** |
| **`LOGIC-12`** | **P0** | Background Sync | Overdue installment schedules were not synchronized on dashboard loads. | Added `InstSvc.sync_overdue_schedules()` hook on admin and seller dashboard initialization. | `eacis/app.py:5040, 7205` | **FIXED** |
| **`SEC-03`** | **P1** | Authorization Bypass | Suspended sellers bypassed portal guards if session was already active. | Updated `enforce_portal_guards()` to immediately block sellers with `seller_verification_status == 'suspended'`, rendering `errors/seller_suspended.html` (403). | `eacis/app.py:900-904` | **FIXED** |
| **`SEC-04`** | **P1** | Open Redirect | Unsanitized `?next=` parameter allowed redirecting users to external malicious domains. | Implemented strict `is_safe_redirect()` function validating path starting with `/` and rejecting `//`, `/\`, and backslashes. | `eacis/app.py:840-855, 1220` | **FIXED** |
| **`SEC-09`** | **P1** | Checkout Gate | Unverified customers were able to bypass email verification and place orders. | Enforced check in `checkout()` blocking unverified customers and redirecting to verification. | `eacis/app.py:2952-2955` | **FIXED** |
| **`SEC-05`** | **P1** | DOM XSS | Unescaped interpolation of item names and attributes in mini-cart and toast UI. | Added global `window.escapeHtml(str)` helper in `base.html` and escaped mini-cart drawer innerHTML templates. | `eacis/templates/base.html:591-605, 695-707` | **FIXED** |
| **`SEC-08`** | **P1** | Secrets & Credentials | Live credentials exposed in `.env`; databases and env not git-ignored. | Updated `.gitignore` to ignore `.env`, `.env.*`, `instance/*.db*`; provided clean placeholders in `.env.example`. Enabled file/console mail mode. | `.gitignore`, `eacis/.env`, `.env.example` | **FIXED** |
| **`UI-03`** | **P2** | Currency Formatting | Inconsistent peso formatting across templates (`PHP 14948.85` vs `₱14,948.85`). | Registered `@app.template_filter('peso')` formatting numbers as `₱{:,.2f}`. | `eacis/app.py:350-355` | **FIXED** |

---

## 3. Automated Regression Verification Suite

A dedicated regression test file, `eacis/tests/test_demo_regressions.py`, was created and executes as part of the standard `pytest` run. It rigorously tests:

1. `test_logic01_seller_refund_execution`: Asserts `finalize_seller_refund` executes cleanly and updates return request status to `refunded`.
2. `test_logic02_installment_refund_capped_and_cancels_schedules`: Asserts installment refund calculates amount actually paid only (downpayment + paid schedules) and marks plan and pending schedules as `cancelled`.
3. `test_logic04_illegal_order_status_jump_rejected`: Asserts an attempt by a seller to jump a `cancelled` order to `delivered` is rejected and order remains `cancelled`.
4. `test_logic03_seller_payout_uses_seller_items_only`: Asserts a seller in a multi-seller order only sees payouts for their specific item line totals, not the full order amount.
5. `test_sec01_cross_tenant_access_control`: Asserts cross-seller ticket hijacking and unauthorized permit downloads return HTTP 403 Forbidden.
6. `test_sec04_open_redirect_protection`: Asserts open redirect payload `//evil.com` is neutralized and routed safely.
7. `test_sec03_suspended_seller_portal_blocked`: Asserts suspended sellers receive an immediate HTTP 403 Forbidden response when accessing the seller portal.

**Pytest Run Result:** `30 passed in 5.75s` (100% passing).

---

## 4. Rehearsal Simulation (`audit/rehearsal_test.py`)

The automated browser click-path script was executed against the active SQLite database (`instance/eacis_dev.db`). It simulates 44 individual interaction steps across 6 roles:

- **Guest:** Storefront browse, product detail inspection, login/register discovery.
- **Customer 1 (Maria Santos):** Full authenticated dashboard, installment schedule review, order inspection, address book, mini-cart, and checkout.
- **Customer 4 (Carlo Reyes):** Unverified email gating demonstration.
- **Seller A (Appliance Hub):** Operational dashboard, order status advancement (`paid` -> `packed`), return inspection, vouchers, isolated payouts, catalog.
- **Seller E (Suspended Depot):** Immediate HTTP 403 suspension page verification.
- **Admin:** Management dashboard, seller verification queue, audit trail, reports, trusted devices.

**Rehearsal Simulation Result:** `0 HTTP 500s`, `0 Infinite Loops`, `44/44 steps passed`.

---

## 5. Security Notice for Platform Administrators

> [!CAUTION]
> **Revoke Gmail App Password Immediately:**
> In the historical repository commit history, a Google App Password (`cmra udys igwg bxzr`) for account `eapplianccommerce@gmail.com` was committed to `eacis/.env`.
> 
> Although local `.env` has now been configured to `MAIL_ENABLED=False` with local file/console delivery (`instance/emails/`), **you must log into your Google Account Security Settings and permanently revoke this App Password** to protect your email account from unauthorized access.
