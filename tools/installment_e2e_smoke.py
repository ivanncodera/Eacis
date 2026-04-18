import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eacis.app import create_app


def _impersonate(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _assert_status(label, response, expected_statuses, failures):
    if response.status_code not in expected_statuses:
        failures.append(f"{label}: expected {sorted(expected_statuses)}, got {response.status_code}")


def run_suite():
    app = create_app()
    failures = []
    notes = []

    with app.app_context():
        from eacis.models.user import User
        from eacis.models.order import Order
        from eacis.models.installment import InstallmentPlan

        customer = User.query.filter_by(role='customer').first()
        seller = User.query.filter_by(role='seller').first()

        if not customer or not seller:
            print('FAIL installment e2e smoke: missing customer or seller account')
            return 1

        installment_order = (
            Order.query.join(InstallmentPlan, InstallmentPlan.order_id == Order.id)
            .filter(Order.customer_id == customer.id)
            .order_by(Order.created_at.desc())
            .first()
        )

    client = app.test_client()

    _impersonate(client, customer.id)

    _assert_status('Customer GET /customer/installments', client.get('/customer/installments'), {200}, failures)

    # Confirm route should require pending checkout + fresh KYC.
    no_pending = client.get('/customer/checkout/installment-confirm', follow_redirects=False)
    _assert_status('GET installment-confirm without pending_checkout', no_pending, {302}, failures)

    with client.session_transaction() as sess:
        sess['pending_checkout'] = {
            'data': {
                'recipient_name': customer.full_name or 'Test Customer',
                'address_line1': 'Sample Address',
                'city_municipality': 'Sample City',
                'province': 'Sample Province',
                'postal_code': '1000',
                'phone': '9000000000',
            },
            'order_total': 12000.00,
            'plan_months': 6,
            'voucher_id': None,
            'loyalty_applied': 0,
        }
        sess.pop('kyc_verified', None)
        sess.pop('kyc_verified_at', None)

    requires_kyc = client.get('/customer/checkout/installment-confirm', follow_redirects=False)
    _assert_status('GET installment-confirm without fresh KYC', requires_kyc, {302}, failures)
    if '/customer/checkout/kyc' not in (requires_kyc.headers.get('Location') or ''):
        failures.append('GET installment-confirm without fresh KYC: expected redirect to /customer/checkout/kyc')

    with client.session_transaction() as sess:
        sess['kyc_verified'] = True
        sess['kyc_verified_at'] = datetime.now(timezone.utc).isoformat()

    confirm_ready = client.get('/customer/checkout/installment-confirm', follow_redirects=False)
    _assert_status('GET installment-confirm with fresh KYC', confirm_ready, {200}, failures)

    if installment_order:
        _assert_status(
            'Customer GET /customer/orders/<installment_order_ref>',
            client.get(f"/customer/orders/{installment_order.order_ref}"),
            {200},
            failures,
        )
    else:
        notes.append('No existing installment order found for sample customer; skipped order detail installment assertion.')

    _impersonate(client, seller.id)
    _assert_status('Seller GET /seller/installment-payments', client.get('/seller/installment-payments'), {200}, failures)

    if failures:
        print('FAIL installment e2e smoke')
        for failure in failures:
            print('-', failure)
        if notes:
            print('NOTES')
            for note in notes:
                print('-', note)
        return 1

    print('PASS installment e2e smoke')
    if notes:
        print('NOTES')
        for note in notes:
            print('-', note)
    print('timestamp', datetime.now(timezone.utc).isoformat())
    return 0


if __name__ == '__main__':
    raise SystemExit(run_suite())
