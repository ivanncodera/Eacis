from datetime import datetime

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

    with app.app_context():
        from eacis.models.user import User
        from eacis.models.product import Product
        from eacis.models.order import Order
        from eacis.models.invoice import Invoice

        customer = User.query.filter_by(role='customer').first()
        seller = User.query.filter_by(role='seller').first()
        admin = User.query.filter_by(role='admin').first()

        if not customer or not seller or not admin:
            print('FAIL missing required role accounts (customer/seller/admin)')
            return 1

        sample_product_ref = None
        sample_order_ref = None
        sample_customer_invoice_ref = None
        sample_seller_invoice_ref = None

        product = Product.query.filter_by(is_active=True).first()
        if product:
            sample_product_ref = product.product_ref

        order = Order.query.filter_by(customer_id=customer.id).first()
        if order:
            sample_order_ref = order.order_ref

        customer_invoice = Invoice.query.filter_by(customer_id=customer.id).first()
        if customer_invoice:
            sample_customer_invoice_ref = customer_invoice.invoice_ref

        seller_invoice = Invoice.query.filter_by(seller_id=seller.id).first()
        if seller_invoice:
            sample_seller_invoice_ref = seller_invoice.invoice_ref

    client = app.test_client()

    # Public bootstrap checks.
    _assert_status('GET /auth/login', client.get('/auth/login'), {200}, failures)
    _assert_status('GET /shop', client.get('/shop'), {200}, failures)
    if sample_product_ref:
        _assert_status(
            'GET /products/<ref>',
            client.get(f'/products/{sample_product_ref}'),
            {200},
            failures,
        )

    # Customer critical path pages.
    _impersonate(client, customer.id)
    _assert_status('Customer GET /cart', client.get('/cart'), {200}, failures)
    _assert_status('Customer GET /checkout', client.get('/checkout'), {200}, failures)
    _assert_status('Customer GET /customer/orders', client.get('/customer/orders'), {200}, failures)
    _assert_status('Customer GET /customer/returns', client.get('/customer/returns'), {200}, failures)
    _assert_status('Customer GET /customer/invoices', client.get('/customer/invoices'), {200}, failures)
    if sample_order_ref:
        _assert_status(
            'Customer GET /customer/orders/<order_ref>',
            client.get(f'/customer/orders/{sample_order_ref}'),
            {200},
            failures,
        )
    if sample_customer_invoice_ref:
        _assert_status(
            'Customer GET /customer/invoices/<invoice_ref>',
            client.get(f'/customer/invoices/{sample_customer_invoice_ref}'),
            {200},
            failures,
        )

    # Seller critical path pages.
    _impersonate(client, seller.id)
    _assert_status('Seller GET /seller/dashboard', client.get('/seller/dashboard'), {200}, failures)
    _assert_status('Seller GET /seller/orders', client.get('/seller/orders'), {200}, failures)
    _assert_status('Seller GET /seller/returns', client.get('/seller/returns'), {200}, failures)
    _assert_status('Seller GET /seller/analytics', client.get('/seller/analytics'), {200}, failures)
    _assert_status('Seller GET /seller/reports/export/excel', client.get('/seller/reports/export/excel'), {200}, failures)
    _assert_status('Seller GET /seller/reports/export/pdf', client.get('/seller/reports/export/pdf'), {200}, failures)
    if sample_seller_invoice_ref:
        _assert_status(
            'Seller GET /seller/invoices/<invoice_ref>',
            client.get(f'/seller/invoices/{sample_seller_invoice_ref}'),
            {200},
            failures,
        )

    # Admin critical path pages.
    _impersonate(client, admin.id)
    _assert_status('Admin GET /admin/dashboard', client.get('/admin/dashboard'), {200}, failures)
    _assert_status('Admin GET /admin/sellers', client.get('/admin/sellers'), {200}, failures)
    _assert_status('Admin GET /admin/audit', client.get('/admin/audit'), {200}, failures)
    _assert_status('Admin GET /admin/reports', client.get('/admin/reports'), {200}, failures)
    _assert_status('Admin GET /admin/reports/export', client.get('/admin/reports/export'), {200}, failures)
    _assert_status('Admin GET /admin/reports/export/excel', client.get('/admin/reports/export/excel'), {200}, failures)
    _assert_status('Admin GET /admin/reports/export/pdf', client.get('/admin/reports/export/pdf'), {200}, failures)

    if failures:
        print('FAIL phase E regression suite')
        for failure in failures:
            print('-', failure)
        return 1

    print('PASS phase E regression suite')
    print('timestamp', datetime.utcnow().isoformat())
    return 0


if __name__ == '__main__':
    raise SystemExit(run_suite())
