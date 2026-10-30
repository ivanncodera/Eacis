import pytest
from datetime import datetime, timedelta
from eacis.app import create_app, db
from eacis.config import Config
from eacis.models.user import User
from eacis.models.product import Product
from eacis.models.order import Order, OrderItem
from eacis.models.return_request import ReturnRequest
from eacis.models.installment import InstallmentPlan, InstallmentSchedule
from eacis.models.inquiry_ticket import InquiryTicket
import eacis.services.return_service as RetSvc

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_ENABLED = False
    FLASK_ENV = 'development'
    SECRET_KEY = 'test-secret'


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_logic01_seller_refund_execution(app, client):
    """LOGIC-01: finalize_seller_refund executes cleanly and updates return status."""
    with app.app_context():
        seller = User(email='seller1@demo.com', role='seller', seller_verification_status='approved')
        seller.set_password('Demo@12345')
        customer = User(email='cust1@demo.com', role='customer', email_verified_at=datetime.utcnow())
        customer.set_password('Demo@12345')
        db.session.add_all([seller, customer])
        db.session.commit()

        prod = Product(product_ref='P-REF-1', seller_id=seller.id, name='Test TV', price=5000.0, stock=10)
        db.session.add(prod)
        db.session.commit()

        order = Order(
            order_ref='ORD-REF-01',
            customer_id=customer.id,
            status='delivered',
            payment_method='full_pay',
            total=5000.0,
            subtotal=5000.0
        )
        db.session.add(order)
        db.session.commit()

        item = OrderItem(order_id=order.id, product_id=prod.id, quantity=1, unit_price=5000.0, subtotal=5000.0)
        db.session.add(item)
        db.session.commit()

        ret = ReturnRequest(
            rrt_ref='RRT-TEST-01',
            order_id=order.id,
            customer_id=customer.id,
            reason='defective',
            description='Screen flickering',
            status='pending'
        )
        db.session.add(ret)
        db.session.commit()

        success, msg = app.finalize_seller_refund(seller, 'RRT-TEST-01')
        assert success is True

        db.session.refresh(ret)
        assert ret.status == 'refunded'


def test_logic02_installment_refund_capped_and_cancels_schedules(app):
    """LOGIC-02: Installment refunds cap at amount actually paid and cancel unpaid schedules."""
    with app.app_context():
        customer = User(email='cust2@demo.com', role='customer', email_verified_at=datetime.utcnow())
        customer.set_password('Demo@12345')
        seller = User(email='seller2@demo.com', role='seller', seller_verification_status='approved')
        seller.set_password('Demo@12345')
        db.session.add_all([customer, seller])
        db.session.commit()

        prod = Product(product_ref='P-REF-2', seller_id=seller.id, name='Aircon', price=12000.0, stock=5)
        db.session.add(prod)
        db.session.commit()

        order = Order(
            order_ref='ORD-INST-01',
            customer_id=customer.id,
            status='delivered',
            payment_method='installment',
            total=12000.0,
            subtotal=12000.0
        )
        db.session.add(order)
        db.session.commit()

        item = OrderItem(order_id=order.id, product_id=prod.id, quantity=1, unit_price=12000.0, subtotal=12000.0)
        db.session.add(item)
        db.session.commit()

        plan = InstallmentPlan(
            order_id=order.id,
            months=10,
            monthly_amount=1000.0,
            downpayment=2000.0,
            total_interest=0.0,
            status='active'
        )
        db.session.add(plan)
        db.session.commit()

        # 1 paid schedule, 9 pending schedules
        s1 = InstallmentSchedule(
            plan_id=plan.id,
            amount=1000.0,
            due_date=datetime.utcnow().date(),
            status='paid',
            paid_at=datetime.utcnow()
        )
        db.session.add(s1)
        for i in range(2, 11):
            s = InstallmentSchedule(
                plan_id=plan.id,
                amount=1000.0,
                due_date=datetime.utcnow().date() + timedelta(days=30*i),
                status='pending'
            )
            db.session.add(s)
        db.session.commit()

        # Total actually paid is downpayment (2000) + schedule 1 (1000) = 3000
        refund_amount = app.calculate_refund_amount(order, seller_id=seller.id)
        assert refund_amount == 3000.0

        # Process refund
        ret = ReturnRequest(
            rrt_ref='RRT-INST-01',
            order_id=order.id,
            customer_id=customer.id,
            reason='defective',
            status='accepted'
        )
        db.session.add(ret)
        db.session.commit()

        success, msg = RetSvc.process_refund(ret.id, seller_id=seller.id)
        assert success is True

        db.session.refresh(plan)
        assert plan.status in ('cancelled', 'refunded')

        unpaid_schedules = InstallmentSchedule.query.filter_by(plan_id=plan.id, status='pending').count()
        assert unpaid_schedules == 0
        cancelled_schedules = InstallmentSchedule.query.filter_by(plan_id=plan.id, status='cancelled').count()
        assert cancelled_schedules == 9


def test_logic04_illegal_order_status_jump_rejected(app, client):
    """LOGIC-04: Seller cannot jump order status from cancelled to delivered."""
    with app.app_context():
        seller = User(email='seller3@demo.com', role='seller', seller_verification_status='approved')
        seller.set_password('Demo@12345')
        customer = User(email='cust3@demo.com', role='customer', email_verified_at=datetime.utcnow())
        customer.set_password('Demo@12345')
        db.session.add_all([seller, customer])
        db.session.commit()

        prod = Product(product_ref='P-REF-3', seller_id=seller.id, name='Fridge', price=8000.0, stock=5)
        db.session.add(prod)
        db.session.commit()

        order = Order(
            order_ref='ORD-CAN-01',
            customer_id=customer.id,
            status='cancelled',
            payment_method='full_pay',
            total=8000.0,
            subtotal=8000.0
        )
        db.session.add(order)
        db.session.commit()

        item = OrderItem(order_id=order.id, product_id=prod.id, quantity=1, unit_price=8000.0, subtotal=8000.0)
        db.session.add(item)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(seller.id)
            sess['_fresh'] = True

        resp = client.post(f'/seller/orders/{order.order_ref}', data={
            'action': 'update_status',
            'status': 'delivered'
        }, follow_redirects=True)

        assert resp.status_code == 200
        db.session.refresh(order)
        # Status must remain cancelled
        assert order.status == 'cancelled'


def test_logic03_seller_payout_uses_seller_items_only(app, client):
    """LOGIC-03: Seller payouts computed from seller's items only, not entire multi-seller order."""
    with app.app_context():
        seller_a = User(email='seller_a@demo.com', role='seller', seller_verification_status='approved')
        seller_a.set_password('Demo@12345')
        seller_b = User(email='seller_b@demo.com', role='seller', seller_verification_status='approved')
        seller_b.set_password('Demo@12345')
        customer = User(email='cust4@demo.com', role='customer', email_verified_at=datetime.utcnow())
        customer.set_password('Demo@12345')
        db.session.add_all([seller_a, seller_b, customer])
        db.session.commit()

        prod_a = Product(product_ref='PA-1', seller_id=seller_a.id, name='Prod A', price=4000.0, stock=10)
        prod_b = Product(product_ref='PB-1', seller_id=seller_b.id, name='Prod B', price=6000.0, stock=10)
        db.session.add_all([prod_a, prod_b])
        db.session.commit()

        order = Order(
            order_ref='ORD-MULTI-01',
            customer_id=customer.id,
            status='delivered',
            payment_method='full_pay',
            total=10000.0,
            subtotal=10000.0
        )
        db.session.add(order)
        db.session.commit()

        item_a = OrderItem(order_id=order.id, product_id=prod_a.id, quantity=1, unit_price=4000.0, subtotal=4000.0)
        item_b = OrderItem(order_id=order.id, product_id=prod_b.id, quantity=1, unit_price=6000.0, subtotal=6000.0)
        db.session.add_all([item_a, item_b])
        db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(seller_a.id)
            sess['_fresh'] = True

        resp = client.get('/seller/payouts')
        assert resp.status_code == 200
        # Seller A's subtotal is 4000 (after 5% platform fee = 3,800.00). It should NOT be based on 10,000.
        assert b'4000.00' in resp.data or b'4,000' in resp.data
        assert b'10000.00' not in resp.data and b'10,000' not in resp.data


def test_sec01_cross_tenant_access_control(app, client):
    """SEC-01: Cross-tenant isolation blocks other sellers from tickets and permits."""
    with app.app_context():
        seller_owner = User(
            email='owner@demo.com',
            role='seller',
            seller_verification_status='approved',
            business_permit_path='owner_permit.pdf'
        )
        seller_owner.set_password('Demo@12345')
        seller_intruder = User(
            email='intruder@demo.com',
            role='seller',
            seller_verification_status='approved'
        )
        seller_intruder.set_password('Demo@12345')
        customer = User(email='cust5@demo.com', role='customer', email_verified_at=datetime.utcnow())
        customer.set_password('Demo@12345')
        db.session.add_all([seller_owner, seller_intruder, customer])
        db.session.commit()

        ticket = InquiryTicket(
            ticket_ref='TCK-101',
            customer_id=customer.id,
            assigned_to=seller_owner.id,
            subject='Product issue',
            description='Help with product',
            status='open'
        )
        db.session.add(ticket)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(seller_intruder.id)
            sess['_fresh'] = True

        # Intruder seller cannot access ticket belonging to owner seller
        resp_ticket = client.get(f'/seller/inquiries/{ticket.ticket_ref}')
        assert resp_ticket.status_code == 403

        # Intruder seller cannot download permit belonging to owner seller
        resp_permit = client.get('/uploads/permits/owner_permit.pdf')
        assert resp_permit.status_code == 403


def test_sec04_open_redirect_protection(app, client):
    """SEC-04: Open redirect attempts (//evil.com) are rejected and routed safely."""
    with app.app_context():
        cust = User(email='safe@demo.com', role='customer', email_verified_at=datetime.utcnow())
        cust.set_password('Demo@12345')
        db.session.add(cust)
        db.session.commit()

    resp = client.post('/auth/login', data={
        'email': 'safe@demo.com',
        'password': 'Demo@12345',
        'next': '//evil.com'
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert '//evil.com' not in resp.location
    assert resp.location.startswith('/')


def test_sec03_suspended_seller_portal_blocked(app, client):
    """SEC-03: Suspended sellers are blocked with HTTP 403 upon portal access."""
    with app.app_context():
        suspended_seller = User(email='suspended@demo.com', role='seller', seller_verification_status='suspended')
        suspended_seller.set_password('Demo@12345')
        db.session.add(suspended_seller)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(suspended_seller.id)
            sess['_fresh'] = True

        resp = client.get('/seller/dashboard')
        assert resp.status_code == 403
        assert b'Suspended' in resp.data or b'suspended' in resp.data
