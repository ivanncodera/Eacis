# E-ACIS Live Demo Guide

**Document Version:** 1.0  
**Target Date:** Demo Day  
**Uniform Password Across ALL Accounts:** `Demo@12345`

---

## 1. Demo Credentials Quick Reference

| Role | Account Name | Email | Scenario & Purpose |
| :--- | :--- | :--- | :--- |
| **System Admin** | System Administrator | `admin@demo.com` | Complete backoffice: seller approvals, reports, security logs, trusted devices |
| **Seller A** | Appliance Hub Philippines | `seller.a@demo.com` | Primary approved seller: orders, status progression, returns desk, payouts, vouchers |
| **Seller B** | Cool Breeze HVAC Corp | `seller.b@demo.com` | Multi-seller partner: split fulfillment, isolated payouts |
| **Seller C** | Pending Kitchens Inc | `seller.c@demo.com` | Pending approval seller (demonstrates portal restriction) |
| **Seller D** | Rejected Electro Outlet | `seller.d@demo.com` | Rejected permit seller |
| **Seller E** | Suspended Depot Ltd | `seller.e@demo.com` | Suspended seller: demonstrates instant HTTP 403 suspension guard |
| **Customer 1** | Maria Santos | `customer1@demo.com` | KYC-approved buyer: active 6-month 0% installment plan, orders, address book |
| **Customer 2** | Juan Dela Cruz | `customer2@demo.com` | Pending KYC installment applicant & active buyer |
| **Customer 3** | Elena Gomez | `customer3@demo.com` | Clean buyer persona ready for live checkout demo |
| **Customer 4** | Carlo Reyes | `customer4@demo.com` | Unverified email: demonstrates checkout blocking gate |
| **Customer 5** | Rosa Rivera | `customer5@demo.com` | Return abuse flagged: demonstrated fraud score & overdue installment plan |

---

## 2. Pre-Demo Setup & Reset (One Command)

To restore the demo environment to a pristine state at any moment (before rehearsal or between presentations), run:

```bash
python demo_seed.py --reset
```

> [!NOTE]
> The reset command automatically creates a backup of `instance/eacis_dev.db` to `instance/eacis_dev.db.bak`, resets all tables, populates realistic catalog items and orders, stamps Alembic to the unified head, and sets all passwords to `Demo@12345`.

---

## 3. Scripted 12-Minute Demo Walkthrough

### Part 1: Public Storefront & Neo-Minimalist UI (2 Minutes)
* **URL:** `http://localhost:5000/` (or your configured port)
* **Persona:** Guest / Unauthenticated Visitor
* **Talking Points & Actions:**
  1. **Clean Hero:** Point out the focused headline (*"Home appliances, paid in easy installments"*), 0% installment badge, and trust indicators.
  2. **Product Catalog:** Navigate to `/shop`. Search for `"Samsung"` or `"Inverter"` using the instant search box. Notice XSS-sanitized autocomplete results with formatted Peso prices (`₱24,999.00`).
  3. **Product Detail:** Click on the **Samsung 55" Crystal UHD 4K Smart TV** (`/products/DEMO-PROD-A1`). Highlight the specifications, 0% installment breakdown table, and verified customer reviews.
  4. **Mini-Cart Drawer:** Click **Add to Bag**. Open the slide-out cart drawer; note clean glassmorphic styling, line totals, and dynamic subtotal.

---

### Part 2: Customer Experience & Installment Transparency (3 Minutes)
* **Persona:** Log in as **Maria Santos** (`customer1@demo.com` / `Demo@12345`)
* **Talking Points & Actions:**
  1. **Customer Dashboard:** Go to `/customer/home`. Highlight personalized recommendations, loyalty point balance (500 pts), and quick navigation.
  2. **Order History:** Visit `/customer/orders`. Open `ORD-DEMO-DELIV` to view the full invoice breakdown, tracking timeline (`TRK-DELIV-001`), and delivery confirmation.
  3. **Installment Schedules:** Navigate to `/customer/installments` (or click on `ORD-DEMO-INST-ACTIVE`).
     - Point out the LG Washer 6-month plan.
     - Show the schedule breakdown: Month 1 & Month 2 are marked **Paid**, while Months 3–6 are **Pending** with explicit due dates.
     - Point out that downpayment + schedules equal the exact financed amount (`₱33,090.00`).
  4. **Support Ticket:** Visit `/customer/inquiries`. View ticket `TCK-DEMO-01` regarding VESA mount compatibility, showing seller Hubert Tan's response.
  5. **Logout:** Click the top-right profile avatar and select **Sign Out**.

---

### Part 3: Seller Fulfillment, Status Engine & Isolated Payouts (3 Minutes)
* **Persona:** Log in as **Seller A (Appliance Hub)** (`seller.a@demo.com` / `Demo@12345`)
* **Talking Points & Actions:**
  1. **Seller Operations Dashboard:** Go to `/seller/dashboard`. Note live metrics: pending orders, return requests, and catalog summary.
  2. **Strict Order Fulfillment:** Navigate to `/seller/orders`.
     - Open `ORD-DEMO-PAID`.
     - Advance status from `paid` to `packed`. Explain that the status machine enforces valid transitions (`paid -> packed -> shipped -> delivered`) and strictly blocks regressions or skipping steps.
  3. **Multi-Seller Order Fulfillment:**
     - Open `ORD-DEMO-MULTI`.
     - Explain: this order contains a Philips Airfryer from Seller A and a Xiaomi Air Purifier from Seller B.
     - Demonstrate that either seller can advance their fulfillment without getting deadlocked.
  4. **Payout Isolation:** Go to `/seller/payouts`.
     - Show the **Available Balance** and **Recent Entries**.
     - Point out that Seller A's payout is calculated strictly from Seller A's items (`₱8,990.00` from the multi-seller order), never the customer's full order total. Multi-tenant financial isolation is 100% maintained.
  5. **Logout:** Sign out from Seller A.

---

### Part 4: Risk Protection, Gating & Suspended Accounts (2 Minutes)
* **Talking Points & Actions:**
  1. **Suspended Seller Gate:**
     - Log in as **Seller E (Suspended Depot)** (`seller.e@demo.com` / `Demo@12345`).
     - Try to access `/seller/dashboard`.
     - **Result:** Immediate **HTTP 403 Forbidden** screen displaying the official suspension notice (`errors/seller_suspended.html`). Access to catalog, payouts, and customer data is completely shut off.
  2. **Unverified Customer Gating:**
     - Attempt to log in as **Customer 4** (`customer4@demo.com` / `Demo@12345`).
     - **Result:** Redirected to the email verification screen. Unverified accounts cannot place orders or checkout.

---

### Part 5: Admin Backoffice & Security Audit Trail (2 Minutes)
* **Persona:** Log in as **System Admin** (`admin@demo.com` / `Demo@12345`)
* **Talking Points & Actions:**
  1. **Admin Dashboard:** Navigate to `/admin/dashboard`. Highlight the platform KPI tiles: GMV, seller count, active installment loans, and the 24-hour OTP delivery metrics (`otp_verify_rate_24h` and `otp_sent_24h`).
  2. **Seller Verification & KYC:** Go to `/admin/sellers`. View **Pending Kitchens Inc** (`seller.c@demo.com`) waiting for permit review. Open their permit document securely.
  3. **Security Audit Log:** Visit `/admin/audit`. Show real-time structured audit events capturing seller logins, permit reviews, and administrative status updates with IP and timestamp metadata.
  4. **Device Trust & Security:** Visit `/admin/trusted-devices`. Show trusted device fingerprints with CSRF-protected revocation actions.

---

## 4. Troubleshooting & Safety Tips During Demo

1. **If you encounter a browser caching issue:** Use an Incognito/Private window so cookies and sessions don't collide between roles.
2. **If an order is accidentally modified during rehearsal:** Simply run `python demo_seed.py --reset` in a terminal; the database will be fresh and consistent in 5 seconds.
3. **Email verification notices:** In development mode (`MAIL_ENABLED=False`), all OTPs and notification emails are safely written to `instance/emails/` and logged to the terminal console without hitting external SMTP servers.
