#!/usr/bin/env python3
"""Debug why /customer/checkout/installment-confirm still redirects when KYC is set in session."""
import sys, os
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eacis.app import create_app

app = create_app()
with app.test_client() as client:
    # find a customer user
    with app.app_context():
        try:
            from eacis.models.user import User
        except Exception:
            from models.user import User
        customer = User.query.filter_by(role='customer').first()
        if not customer:
            print('No customer account found; create one quickly')
            customer = User(email='dbg_customer@example.com', role='customer', full_name='Dbg Customer')
            customer.set_password('password')
            from eacis.extensions import db
            db.session.add(customer)
            db.session.commit()

    # impersonate
    with client.session_transaction() as sess:
        sess['_user_id'] = str(customer.id)
        sess['_fresh'] = True

    # set pending_checkout
    with client.session_transaction() as sess:
        sess['pending_checkout'] = {'data': {'recipient_name': customer.full_name or customer.computed_full_name, 'address_line1': 'Test', 'postal_code': '1000', 'phone': '09170000000'}, 'order_total': 1000.0, 'plan_months': 3}
        # set kyc as fresh
        sess['kyc_verified'] = True
        sess['kyc_verified_at'] = datetime.now(timezone.utc).isoformat()

    resp = client.get('/customer/checkout/installment-confirm', follow_redirects=False)
    print('STATUS', resp.status_code)
    print('LOCATION', resp.headers.get('Location'))
    try:
        print('BODY_SNIPPET', resp.get_data(as_text=True)[:800])
    except Exception:
        pass
