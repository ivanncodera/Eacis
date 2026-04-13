from pathlib import Path


def run_checks():
    app_py = Path(__file__).resolve().parents[1] / 'eacis' / 'app.py'
    source = app_py.read_text(encoding='utf-8')
    failures = []

    checks = [
        (
            'customer invoice detail ownership',
            "def customer_invoice_detail(invoice_ref):" in source
            and "getattr(current_user, 'role', None) == 'customer'" in source
            and "Invoice.query.filter_by(invoice_ref=invoice_ref, customer_id=current_user.id).first()" in source,
        ),
        (
            'seller invoice detail ownership',
            "def seller_invoice_detail(invoice_ref):" in source
            and "getattr(current_user, 'role', None) == 'seller'" in source
            and "Invoice.query.filter_by(invoice_ref=invoice_ref, seller_id=current_user.id).first()" in source,
        ),
        (
            'customer order detail ownership',
            "def customer_order_detail(order_ref):" in source
            and "Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first()" in source,
        ),
        (
            'seller return ownership enforcement',
            "def seller_returns_update(rrt_ref):" in source
            and "seller_has_item = False" in source
            and "if not seller_has_item:" in source,
        ),
    ]

    for label, ok in checks:
        if not ok:
            failures.append(label)

    if failures:
        for failure in failures:
            print('FAIL', failure)
        return 1

    print('PASS object-level access checks')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_checks())
