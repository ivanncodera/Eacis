# OTP Emailer Implementation Plan

## Objective
Add a secure email-based OTP layer to E-ACIS for authentication and high-risk account actions, with ecommerce-grade UX, abuse controls, auditability, and rollback-safe rollout.

## Current State Summary
- Authentication is password-based via `/auth/login`.
- Registration exists for customers and sellers via `/auth/register/customer` and `/auth/register/seller`.
- The system already has security-sensitive flows such as seller security settings, installment KYC, profile updates, order cancellation, and seller/admin operations.
- There is currently no OTP model, no email delivery pipeline, and no dedicated verification session flow.

## OTP Strategy
Use email OTP as a step-up verification layer, not as a replacement for passwords.

Recommended policy:
- Password remains the primary credential.
- OTP is required for high-risk actions and optional for lower-risk trust-building flows.
- OTP codes are short-lived, one-time, hashed at rest, and rate-limited.
- OTP requests are audit logged and tied to a purpose.

## Scenarios That Should Use OTP

### Mandatory OTP Scenarios
1. New account email verification after registration.
2. First login on a new device or untrusted browser session.
3. Password reset flow.
4. Email address change.
5. Password change after successful password entry.
6. Seller security-sensitive account changes, such as:
   - business profile email updates
   - payout or settlement configuration changes if added later
   - bank / disbursement changes if added later
7. Admin-level privileged actions if the platform exposes them through the UI.

### Recommended OTP Scenarios for Ecommerce High Standards
1. Checkout confirmation for installment purchases.
2. High-risk customer account changes, such as address-book or identity fields if the business wants stronger assurance.
3. Order cancellation for paid orders.
4. Refund initiation or refund approval.
5. Return abuse escalation or dispute actions.
6. Seller verification step-up when uploading compliance documents or changing verified business details.
7. Recovery of account access after suspicious activity or repeated login failures.

### Optional / Policy-Driven Scenarios
1. Remember-device trust renewal after a configurable period.
2. Login from a new country, IP range, or browser fingerprint.
3. Bulk seller operations such as mass order updates, if ever exposed.

## Data Model Design
Add a dedicated OTP model, not a loose session-only implementation.

Suggested `OtpChallenge` fields:
- `id`
- `user_id`
- `email`
- `purpose` with values such as `login`, `register`, `password_reset`, `email_change`, `step_up`, `installment_confirm`
- `code_hash`
- `expires_at`
- `consumed_at`
- `attempt_count`
- `max_attempts`
- `sent_to`
- `ip_address`
- `user_agent`
- `trusted_device_token` or `remembered_device_id` if you support trusted devices
- `created_at`
- `verified_at`
- `failure_reason`
- `metadata` JSON for extra context

Recommended related table:
- `OtpAuditLog` if you want separate reporting from generic audit logs.

Important rule:
- Store only a hash of the OTP, never the plaintext code.
- Use a pepper or server secret when hashing to reduce offline risk.

## Email Delivery Design
Use an email service abstraction rather than sending mail directly from route handlers.

Suggested service responsibilities:
- generate OTP code
- hash and save OTP record
- render branded email template
- send email through the provider
- handle retries and provider errors
- write audit events

Recommended provider options:
- transactional email service with templates and delivery metrics
- SMTP only as a fallback, not the preferred primary option

Email content standards:
- clear purpose line
- code displayed prominently
- expiry window stated
- user guidance if they did not request the code
- no sensitive account details in the email body

## UX Flow by Scenario

### 1. Registration Verification
Customer and seller registrations should:
- create the account in a pending / unverified state, or
- create the account and require OTP before activating access

Recommended flow:
1. User submits registration form.
2. System creates a pending account.
3. System sends OTP to the registration email.
4. User enters OTP on a verification page.
5. On success, account becomes active and user is logged in.

Why this matters:
- prevents disposable or mistyped emails from becoming active accounts
- gives better fraud control

### 2. Login Step-Up
Login should be a two-stage process when OTP is required.

Recommended flow:
1. User submits email + password.
2. If the session is trusted and risk is low, log in normally.
3. If the session is new, suspicious, or policy requires it, create OTP challenge.
4. Redirect to OTP entry screen.
5. On success, finish login and mark device as trusted if allowed.

Risk signals:
- new device or browser
- new IP or geolocation
- too many failed login attempts
- seller/admin roles
- unusual checkout or refund activity

### 3. Password Reset
Recommended flow:
1. User requests password reset.
2. Send OTP to email.
3. User enters OTP.
4. User sets a new password.
5. Invalidate all active sessions if possible.

Security notes:
- OTP must expire quickly.
- Reset tokens should be single-use.
- Prefer separate reset link + OTP for stronger assurance if you want a higher standard.

### 4. Email Change
Recommended flow:
1. User requests email update.
2. Confirm current password.
3. Send OTP to the new email address.
4. User verifies OTP on the new address.
5. Update email only after successful verification.

### 5. Password Change
Recommended flow:
1. User enters current password.
2. Send OTP to the registered email.
3. User confirms OTP.
4. Then allow password update.
5. Revoke existing sessions if appropriate.

### 6. Seller Security and Compliance Actions
Use OTP for seller actions that could affect disbursement, identity, or compliance.

Recommended examples:
- business email update
- payout contact update
- compliance document changes
- verification status changes
- account recovery after seller verification lockouts

### 7. Checkout / Installment Step-Up
For premium ecommerce standards, use OTP as a final confirmation on installment checkout.

Recommended flow:
1. Customer chooses installment.
2. Customer completes KYC or identity verification.
3. System sends OTP to email before final order placement.
4. User enters OTP on confirm page.
5. Order is created only after OTP success.

This is optional if KYC already provides enough friction, but it is a strong anti-fraud control for installment purchases.

### 8. Sensitive Post-Auth Actions
Consider OTP before:
- paid order cancellation requests
- refund submissions
- high-value support actions
- address changes after order placement
- bank or wallet changes

## Route Plan
Suggested new routes:
- `GET /auth/otp/verify` - OTP entry form
- `POST /auth/otp/send` - request a new code
- `POST /auth/otp/verify` - submit code
- `POST /auth/otp/resend` - reissue code with throttling
- `GET /auth/forgot-password` - request password reset
- `POST /auth/forgot-password` - send reset OTP
- `GET /auth/reset-password` - reset form after OTP verification

Optional flow-specific routes:
- `GET /auth/verify-email`
- `GET /auth/step-up`
- `GET /customer/checkout/installment-otp`
- `GET /seller/security/otp`

## Session Design
Add explicit session state flags so the OTP flow remains deterministic.

Suggested session keys:
- `otp_challenge_id`
- `otp_purpose`
- `otp_verified`
- `otp_verified_at`
- `otp_expires_at`
- `pending_login_user_id`
- `pending_action_payload`
- `trusted_device_id`

Rules:
- Never store the code in session.
- Never keep a successful OTP state longer than necessary.
- Clear OTP session state after success or expiration.

## Abuse Protection
Must-have controls:
- rate limit send attempts per user, email, IP, and purpose
- rate limit verify attempts per challenge
- lock out repeated failures with exponential backoff
- invalidate older OTPs when a new one is generated
- prevent code reuse
- require minimum cooldown between resend requests
- block OTP generation for unregistered or mismatched purposes

Recommended controls:
- captcha after repeated OTP request abuse
- device trust scoring
- IP reputation checks if available
- audit alerts for repeated OTP failures

## Audit and Logging
Log each OTP lifecycle event:
- requested
- sent
- resend requested
- verified
- expired
- failed verification
- locked out
- purpose mismatch

This should integrate with the existing audit trail pattern used elsewhere in the app.

## Templates To Add
Suggested templates:
- `auth/otp_verify.html`
- `auth/otp_sent.html`
- `auth/password_reset_request.html`
- `auth/password_reset_verify.html`
- `auth/password_reset_new.html`
- `auth/email_change_verify.html`

UI standards:
- six-digit code entry with auto-advance
- paste support
- resend countdown
- clear expiry indicator
- accessible error states
- mobile-first layout
- branded empty/error/success states

## Email Template Standards
Use separate branded templates for:
- registration OTP
- login OTP
- password reset OTP
- email change OTP
- installment confirmation OTP
- security step-up OTP

Each email should contain:
- purpose
- code
- expiry window
- anti-phishing warning
- support link
- no clickable OTP-only bypass if the policy requires manual input

## Best-Practice Security Standards
1. OTP should be 6 digits minimum, 8 digits for higher-risk flows if you want stronger resistance.
2. Expiry should be short, typically 5 to 10 minutes.
3. Codes should be single-use only.
4. Rate limit send and verify attempts.
5. Hash OTP at rest.
6. Use HTTPS only.
7. Re-authenticate before high-risk changes.
8. Invalidate sessions after password or email changes.
9. Prefer step-up OTP over blanket OTP on every login, unless business policy requires universal MFA.
10. Record all events for audit and fraud review.

## Suggested Rollout Phases

### Phase 1 - Foundation
- Add OTP model and migration.
- Add email service abstraction.
- Add configuration values.
- Add hash/verify helpers.
- Add audit events.

### Phase 2 - Core Authentication
- Registration email verification.
- Login step-up OTP.
- Password reset with OTP.

### Phase 3 - High-Risk Account Actions
- Email change verification.
- Password change step-up.
- Seller security actions.
- Admin privileged action protection.

### Phase 4 - Ecommerce Hardening
- Installment checkout confirmation OTP.
- Paid order cancellation step-up.
- Refund and return escalation OTP.
- Trusted device policy.

### Phase 5 - Monitoring and Optimization
- OTP analytics.
- drop-off tracking.
- resend failure analysis.
- fraud/risk tuning.

## Testing Plan
Must test:
- successful OTP send and verify
- expired OTP
- wrong OTP
- too many attempts
- resend cooldown
- login step-up flow
- registration verification flow
- password reset flow
- email change flow
- installment checkout OTP flow
- seller/admin high-risk action flow
- audit logs created for each event

Add end-to-end tests for:
- customer registration -> OTP -> login
- login from new device -> OTP -> dashboard
- password reset -> OTP -> password change
- seller security change -> OTP -> save
- installment confirmation -> OTP -> order placement

## Acceptance Criteria
The OTP implementation is complete when:
- OTP is enforced for the chosen scenarios.
- OTPs are emailed reliably and expire safely.
- All sensitive flows have consistent UX and audit trails.
- Failed attempts are rate-limited.
- No plaintext OTP is stored.
- User sessions behave correctly after verification.
- Tests cover all critical OTP journeys.

## Recommended Scope Decision
For E-ACIS, I would start with this minimum high-value set:
1. Registration email verification.
2. Login step-up OTP for new devices or suspicious sessions.
3. Password reset OTP.
4. Email change OTP.
5. Seller/admin step-up OTP for sensitive changes.
6. Optional installment confirmation OTP for high-risk checkout.

That set gives strong ecommerce security without over-fricting every purchase.
