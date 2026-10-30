from eacis.app import create_app
from eacis.extensions import db
from eacis.models.voucher import Voucher
from eacis.models.order import Order
from eacis.models.installment import InstallmentPlan
from eacis.models.user import User


def test_unclaimed_voucher_exists():
    app = create_app()
    with app.app_context():
        v = Voucher.query.filter_by(code='UNCLAIM5').first()
        assert v is not None
        # should be active and unused
        assert v.is_active
        assert (v.uses_count or 0) == 0


def test_unpaid_and_past_due_orders():
    app = create_app()
    with app.app_context():
        o4 = Order.query.filter_by(order_ref='ORD-1004').first()
        o5 = Order.query.filter_by(order_ref='ORD-1005').first()
        assert o4 is not None and o4.status == 'pending'
        assert o5 is not None and o5.status == 'past_due'


def test_installment_plans_present_and_statuses():
    app = create_app()
    with app.app_context():
        p_paid = InstallmentPlan.query.join(Order).filter(Order.order_ref == 'ORD-2001').first()
        p_active = InstallmentPlan.query.join(Order).filter(Order.order_ref == 'ORD-2002').first()
        p_default = InstallmentPlan.query.join(Order).filter(Order.order_ref == 'ORD-2003').first()
        assert p_paid is not None and p_paid.status == 'completed'
        assert p_active is not None and p_active.status == 'active'
        assert p_default is not None and p_default.status == 'defaulted'


def test_seller_and_admin_demo_metadata():
    app = create_app()
    with app.app_context():
        seller = User.query.filter_by(email='seller@verified.com').first()
        admin = User.query.filter_by(email='admin@eacis.com').first()
        assert seller is not None
        assert admin is not None
        assert seller.phone is not None
        assert seller.business_permit_path is not None
        assert admin.email_verified_at is not None
