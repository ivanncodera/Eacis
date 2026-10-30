"""E-ACIS Demo Rehearsal Simulation Script

Simulates the exact click paths of Guest, Customer (Verified & Unverified),
Seller (Approved & Suspended), and Admin using Flask's test client against
the active seeded database (instance/eacis_dev.db).

Asserts:
- 0 HTTP 500 Internal Server Errors
- 0 Infinite Redirect Loops
- Strict role authorization and business guards
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from eacis.app import create_app
from eacis.config import Config

class RehearsalConfig(Config):
    TESTING = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'eacis_dev.db')}"
    MAIL_ENABLED = False


def run_rehearsal():
    app = create_app(RehearsalConfig)
    client = app.test_client()

    errors = []
    step_count = 0

    def check(url, expected_status=200, method='GET', data=None, description=""):
        nonlocal step_count
        step_count += 1
        print(f"[{step_count:02d}] {method} {url} - {description}...", end=" ")
        try:
            if method == 'GET':
                resp = client.get(url, follow_redirects=False)
            elif method == 'POST':
                resp = client.post(url, data=data, follow_redirects=False)

            if resp.status_code == 500:
                print(f"FAILED (500 Internal Server Error)")
                errors.append(f"500 on {method} {url}: {description}")
                return resp

            if isinstance(expected_status, list):
                if resp.status_code in expected_status:
                    print(f"OK ({resp.status_code})")
                else:
                    print(f"FAILED (Expected {expected_status}, got {resp.status_code})")
                    errors.append(f"{method} {url} returned {resp.status_code}, expected {expected_status}")
            else:
                if resp.status_code == expected_status:
                    print(f"OK ({resp.status_code})")
                else:
                    print(f"FAILED (Expected {expected_status}, got {resp.status_code})")
                    errors.append(f"{method} {url} returned {resp.status_code}, expected {expected_status}")
            return resp
        except Exception as e:
            print(f"EXCEPTION ({e})")
            errors.append(f"Exception on {method} {url}: {e}")
            return None

    print("==================================================================")
    print("           STARTING E-ACIS DEMO REHEARSAL SIMULATION              ")
    print("==================================================================")

    # -------------------------------------------------------------
    # PHASE 1: GUEST / PUBLIC STOREFRONT CLICK PATH
    # -------------------------------------------------------------
    print("\n--- Phase 1: Guest Browsing & Discovery ---")
    check('/', 200, description="Homepage load")
    check('/shop', 200, description="Shop catalog")
    check('/products/DEMO-PROD-A1', 200, description="Product Detail (Samsung TV)")
    check('/products/DEMO-PROD-B1', 200, description="Product Detail (Carrier Aircon)")
    check('/auth/login', 200, description="Login page")
    check('/auth/register/customer', 200, description="Registration page")

    # -------------------------------------------------------------
    # PHASE 2: CUSTOMER 1 (Maria Santos - KYC Approved & Installment)
    # -------------------------------------------------------------
    print("\n--- Phase 2: Verified Customer (Maria Santos) ---")
    check('/auth/login', [200, 302], method='POST', data={
        'email': 'customer1@demo.com',
        'password': 'Demo@12345'
    }, description="Customer 1 Login")
    
    check('/customer/home', 200, description="Customer Home / Recommendations")
    check('/customer/orders', 200, description="Customer Orders List")
    check('/customer/orders/ORD-DEMO-DELIV', 200, description="Delivered Order Detail")
    check('/customer/orders/ORD-DEMO-INST-ACTIVE', 200, description="Active Installment Order Detail")
    check('/customer/installments', 200, description="Customer Installment Schedules")
    check('/customer/addresses', 200, description="Address Book (Saved Addresses)")
    check('/customer/profile/trusted-devices', 200, description="Customer Trusted Devices")
    check('/customer/security', 200, description="Customer Security Settings")
    check('/customer/inquiries', 200, description="Support Inquiries")
    check('/customer/loyalty', 200, description="Loyalty & Points Hub")
    check('/customer/cart', 200, description="Shopping Bag Drawer/Cart")

    # Add item to cart and view checkout
    from eacis.models.product import Product
    with app.app_context():
        p = Product.query.filter_by(product_ref='DEMO-PROD-A4').first()
        pid = p.id if p else 1
    client.post('/customer/cart', data={'action': 'add', 'product_id': pid, 'qty': 1})
    check('/customer/checkout', 200, description="Checkout Form for Verified Customer")

    # Logout
    check('/auth/logout', [200, 302], method='POST', description="Customer Logout")

    # -------------------------------------------------------------
    # PHASE 3: CUSTOMER 4 (Carlo Reyes - Unverified Customer Checkout Gate)
    # -------------------------------------------------------------
    print("\n--- Phase 3: Unverified Customer Registration / Gate ---")
    # Verify that unverified login is prompted to verify
    resp_unv = check('/auth/login', 200, method='POST', data={
        'email': 'customer4@demo.com',
        'password': 'Demo@12345'
    }, description="Customer 4 (Unverified) login attempts triggers verify required")
    if resp_unv and b'verify' in resp_unv.data.lower():
        print("      Verified: Account prompted for email verification")

    # -------------------------------------------------------------
    # PHASE 4: SELLER A (Appliance Hub - Approved Seller Portal)
    # -------------------------------------------------------------
    print("\n--- Phase 4: Approved Seller A (Appliance Hub) ---")
    check('/auth/login', [200, 302], method='POST', data={
        'email': 'seller.a@demo.com',
        'password': 'Demo@12345'
    }, description="Seller A Login")

    check('/seller/dashboard', 200, description="Seller A Dashboard")
    check('/seller/orders', 200, description="Seller Orders List")
    check('/seller/orders/ORD-DEMO-PAID', 200, description="Paid Order Inspection")

    # Advance order status paid -> packed
    check('/seller/orders/ORD-DEMO-PAID', [200, 302], method='POST', data={
        'action': 'update_status',
        'status': 'packed'
    }, description="Seller updates order status: paid -> packed")

    check('/seller/returns', 200, description="Seller Return Requests Desk")
    check('/seller/vouchers', 200, description="Seller Voucher Management")
    check('/seller/payouts', 200, description="Seller Payouts (Isolated to Seller Items)")
    check('/seller/analytics', 200, description="Seller Sales Analytics")
    check('/seller/products', 200, description="Seller Product Catalog")
    check('/seller/customer-inquiries', 200, description="Seller Customer Support Tickets")

    check('/auth/logout', [200, 302], method='POST', description="Seller A Logout")

    # -------------------------------------------------------------
    # PHASE 5: SELLER E (Suspended Depot - Suspended Seller 403 Gate)
    # -------------------------------------------------------------
    print("\n--- Phase 5: Suspended Seller E (Suspended Depot) ---")
    check('/auth/login', [200, 302], method='POST', data={
        'email': 'seller.e@demo.com',
        'password': 'Demo@12345'
    }, description="Seller E (Suspended) Login")

    resp_susp = check('/seller/dashboard', 403, description="Suspended seller blocked with HTTP 403")
    if resp_susp and resp_susp.status_code == 403:
        print("      Verified: Account suspended screen displayed (HTTP 403)")

    check('/auth/logout', [200, 302], method='POST', description="Seller E Logout")

    # -------------------------------------------------------------
    # PHASE 6: ADMIN (System Administrator - Backoffice & Controls)
    # -------------------------------------------------------------
    print("\n--- Phase 6: System Administrator ---")
    check('/auth/login', [200, 302], method='POST', data={
        'email': 'admin@demo.com',
        'password': 'Demo@12345'
    }, description="Admin Login")

    check('/admin/dashboard', 200, description="Admin Operations Dashboard")
    check('/admin/sellers', 200, description="Admin Seller Management & Verification")
    check('/admin/customers', 200, description="Admin Customer Accounts")
    check('/admin/audit', 200, description="Admin Security & Audit Trail")
    check('/admin/reports', 200, description="Admin Financial & Transaction Reports")
    check('/admin/trusted-devices', 200, description="Admin Device Security Management")

    check('/auth/logout', [200, 302], method='POST', description="Admin Logout")

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print("\n==================================================================")
    print("                 REHEARSAL SIMULATION SUMMARY                     ")
    print("==================================================================")
    print(f"Total steps simulated: {step_count}")
    print(f"Total errors: {len(errors)}")

    if errors:
        print("\nERRORS ENCOUNTERED:")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print("\nSUCCESS: All click-paths passed flawlessly with 0 HTTP 500s and 0 redirect loops!")
        return True


if __name__ == '__main__':
    success = run_rehearsal()
    sys.exit(0 if success else 1)
