import os
import sys
import json
import shutil
from datetime import datetime, timedelta
from decimal import Decimal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

# Ensure we ONLY touch instance/audit_copy.db and audit/logs/mail
ORIG_DB = os.path.join(ROOT, 'instance', 'eacis_dev.db')
AUDIT_DB = os.path.join(ROOT, 'instance', 'audit_copy.db')
MAIL_DIR = os.path.join(ROOT, 'audit', 'logs', 'mail')
os.makedirs(MAIL_DIR, exist_ok=True)
shutil.copyfile(ORIG_DB, AUDIT_DB)

os.environ['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{AUDIT_DB.replace(os.sep, '/')}"
os.environ['DATABASE_URL'] = f"sqlite:///{AUDIT_DB.replace(os.sep, '/')}"
os.environ['MAIL_MODE'] = 'file'
os.environ['MAIL_OUTPUT_DIR'] = MAIL_DIR

from eacis.config import Config
from eacis.app import create_app
from eacis.extensions import db
from eacis.models import (
    User, Product, Order, OrderItem, Cart, InstallmentPlan, InstallmentSchedule,
    ReturnRequest, Voucher, VoucherUsageLog, LoyaltyTransaction, InquiryTicket,
    TrustedDevice, OtpChallenge, Invoice
)
from eacis.services import return_service as RetSvc

class AuditConfig(Config):
    TESTING = True
    SECRET_KEY = 'audit-secret-key'
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{AUDIT_DB.replace(os.sep, '/')}"
    MAIL_MODE = 'file'
    MAIL_OUTPUT_DIR = MAIL_DIR
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

app = create_app(AuditConfig)

results = {
    'db_uri_verified': app.config['SQLALCHEMY_DATABASE_URI'],
    'role_matrix': {},
    'flow_checks': {},
    'financial_reconciliation': {},
}

def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

with app.app_context():
    c_dbg = app.test_client()
    login_as(c_dbg, 1)
    r_dbg = c_dbg.get('/api/session')
    results['auth_debug'] = {
        'user_1_in_db': bool(db.session.get(User, 1)),
        'api_session_resp': r_dbg.get_json()
    }
    # Create test fixtures on audit_copy.db for every role variant
    admin = User.query.filter_by(role='admin').first()
    seller_approved = User.query.filter_by(email='seller@verified.com').first()
    seller_pending = User.query.filter_by(email='seller@pending.com').first()
    customer_verified = User.query.filter_by(email='customer@demo.com').first()
    if customer_verified and not customer_verified.email_verified_at:
        customer_verified.email_verified_at = datetime.utcnow()

    # Additional test role users in audit_copy.db
    seller_rejected = User(
        email='seller_rejected@audit.local',
        role='seller',
        business_name='Rejected Shop',
        seller_verification_status='rejected',
        is_active=True
    )
    seller_rejected.set_password('Seller123!')

    seller_suspended = User(
        email='seller_suspended@audit.local',
        role='seller',
        business_name='Suspended Shop',
        seller_verification_status='suspended',
        is_active=False
    )
    seller_suspended.set_password('Seller123!')

    customer_unverified = User(
        email='cust_unverified@audit.local',
        role='customer',
        full_name='Unverified Buyer',
        email_verified_at=None,
        is_active=True
    )
    customer_unverified.set_password('Customer123!')

    customer_kyc_ok = User(
        email='cust_kyc@audit.local',
        role='customer',
        full_name='KYC Approved Buyer',
        email_verified_at=datetime.utcnow(),
        business_permit_path='permits/kyc_cust_test.pdf',
        address_line1='100 Main St',
        barangay='Bel-Air',
        city_municipality='Makati',
        province='Metro Manila',
        postal_code='1209',
        phone='09170001111',
        is_active=True
    )
    customer_kyc_ok.set_password('Customer123!')

    customer_kyc_expired = User(
        email='cust_kyc_exp@audit.local',
        role='customer',
        full_name='KYC Expired Buyer',
        email_verified_at=datetime.utcnow(),
        business_permit_path='permits/kyc_cust_exp.pdf',
        is_active=True
    )
    customer_kyc_expired.set_password('Customer123!')

    db.session.add_all([
        seller_rejected, seller_suspended,
        customer_unverified, customer_kyc_ok, customer_kyc_expired
    ])
    db.session.commit()

    roles = {
        'guest': None,
        'customer_unverified': customer_unverified.id,
        'customer_verified': customer_verified.id,
        'customer_kyc_ok': customer_kyc_ok.id,
        'customer_kyc_expired': customer_kyc_expired.id,
        'seller_pending': seller_pending.id,
        'seller_approved': seller_approved.id,
        'seller_rejected': seller_rejected.id,
        'seller_suspended': seller_suspended.id,
        'admin': admin.id,
    }
    seller_suspended_id = seller_suspended.id
    seller_pending_id = seller_pending.id
    seller_rejected_id = seller_rejected.id
    seller_approved_id = seller_approved.id
    customer_kyc_ok_id = customer_kyc_ok.id
    admin_id = admin.id

# Run HTTP test_client probes OUTSIDE outer app_context so flask.g._login_user is isolated per request!
probe_paths = [
    ('GET', '/'),
    ('GET', '/shop'),
    ('GET', '/cart'),
    ('GET', '/checkout'),
    ('GET', '/customer/dashboard'),
    ('GET', '/customer/orders'),
    ('GET', '/customer/installments'),
    ('GET', '/customer/returns'),
    ('GET', '/customer/loyalty'),
    ('GET', '/customer/profile'),
    ('GET', '/seller/dashboard'),
    ('GET', '/seller/products'),
    ('GET', '/seller/orders'),
    ('GET', '/seller/returns'),
    ('GET', '/seller/payouts'),
    ('GET', '/seller/verification'),
    ('GET', '/admin/dashboard'),
    ('GET', '/admin/sellers'),
    ('GET', '/admin/users'),
    ('GET', '/admin/reports'),
    ('GET', '/admin/audit'),
]

for role_name, uid in roles.items():
    results['role_matrix'][role_name] = {}
    c = app.test_client()
    if uid is not None:
        login_as(c, uid)
    for method, path in probe_paths:
        resp = c.open(path, method=method, follow_redirects=False)
        loc = resp.headers.get('Location', '')
        results['role_matrix'][role_name][f"{method} {path}"] = {
            'status': resp.status_code,
            'redirect': loc
        }

# 2. Check SEC-03: Suspended seller portal access
c_susp = app.test_client()
login_as(c_susp, seller_suspended_id)
resp_susp_inactive = c_susp.get('/seller/orders', follow_redirects=False)
with app.app_context():
    s_u = db.session.get(User, seller_suspended_id)
    s_u.is_active = True
    db.session.commit()
resp_susp_active = c_susp.get('/seller/orders', follow_redirects=False)
results['flow_checks']['SEC_03_suspended_seller'] = {
    'when_is_active_false_status': resp_susp_inactive.status_code,
    'when_is_active_false_redirect': resp_susp_inactive.headers.get('Location', ''),
    'when_is_active_true_status_suspended': resp_susp_active.status_code,
    'when_is_active_true_redirect': resp_susp_active.headers.get('Location', ''),
}

# 3. Check SEC-01a: Permit/KYC file access across sellers
permits_dir = os.path.join(app.instance_path, 'uploads', 'permits')
os.makedirs(permits_dir, exist_ok=True)
test_permit_file = os.path.join(permits_dir, 'audit_temp_kyc.txt')
with open(test_permit_file, 'w') as f:
    f.write('DUMMY_KYC_DOCUMENT')
try:
    c_pend = app.test_client()
    login_as(c_pend, seller_pending_id)
    r_permit = c_pend.get('/uploads/permits/audit_temp_kyc.txt')
    body_bytes = r_permit.get_data()
    r_permit.close()
    results['flow_checks']['SEC_01a_pending_seller_reads_any_permit_or_kyc'] = {
        'status': r_permit.status_code,
        'body_len': len(body_bytes)
    }
finally:
    if os.path.exists(test_permit_file):
        os.remove(test_permit_file)

# 4. Check SEC-01b: Seller Inquiry IDOR
with app.app_context():
    ticket = InquiryTicket.query.first()
    t_ref = ticket.ticket_ref if ticket else None
    t_assigned = ticket.assigned_to if ticket else None
    sr = db.session.get(User, seller_rejected_id)
    sr.seller_verification_status = 'approved'
    db.session.commit()
if t_ref:
    c_other_seller = app.test_client()
    login_as(c_other_seller, seller_rejected_id)
    r_inq = c_other_seller.get(f'/seller/inquiries/{t_ref}')
    results['flow_checks']['SEC_01b_seller_inquiry_idor'] = {
        'ticket_ref': t_ref,
        'assigned_to': t_assigned,
        'other_seller_id': seller_rejected_id,
        'status': r_inq.status_code
    }
with app.app_context():
    sr = db.session.get(User, seller_rejected_id)
    sr.seller_verification_status = 'rejected'
    db.session.commit()

# 5. Check SEC-02: Missing /uploads/returns/<filename> route
c_admin = app.test_client()
login_as(c_admin, admin_id)
r_ret_upload = c_admin.get('/uploads/returns/sample_evidence.jpg')
results['flow_checks']['SEC_02_missing_returns_upload_route'] = {
    'status': r_ret_upload.status_code
}

# 6. Check LOGIC-01: Seller refund crashes with NameError ('finalize_seller_refund')
with app.app_context():
    rrt = ReturnRequest.query.first()
    if rrt:
        rrt.status = 'accepted'
        db.session.commit()
        rrt_ref_val = rrt.rrt_ref
    else:
        rrt_ref_val = None
if rrt_ref_val:
    c_sel = app.test_client()
    login_as(c_sel, seller_approved_id)
    with c_sel.session_transaction() as sess:
        sess['seller_refund_otp_verified'] = True
        sess['seller_refund_otp_verified_at'] = datetime.utcnow().isoformat()
    try:
        r_otp = c_sel.post(f'/seller/returns/{rrt_ref_val}', data={'action': 'refund', 'notes': 'Refunding now'})
        results['flow_checks']['LOGIC_01_finalize_seller_refund'] = {
            'status': r_otp.status_code,
            'error': None
        }
    except Exception as exc:
        results['flow_checks']['LOGIC_01_finalize_seller_refund'] = {
            'status': 500,
            'error': f"{type(exc).__name__}: {exc}"
        }

# 8. Check LOGIC-04: Order state machine jump from 'cancelled' directly to 'delivered'
with app.app_context():
    canc_order = Order.query.filter_by(status='cancelled').first()
    canc_ref = canc_order.order_ref if canc_order else None
if canc_ref:
    c_sel = app.test_client()
    login_as(c_sel, seller_approved_id)
    r_jump = c_sel.post(
        f'/seller/orders/{canc_ref}',
        data={'status': 'delivered', 'tracking_number': 'TRK-ILLEGAL'},
        follow_redirects=False
    )
    with app.app_context():
        canc_order = Order.query.filter_by(order_ref=canc_ref).first()
        results['flow_checks']['LOGIC_04_cancelled_to_delivered_jump'] = {
            'order_ref': canc_ref,
            'http_status': r_jump.status_code,
            'order_status_after': canc_order.status,
        }

# 9. Check LOGIC-06: Partial cart checkout wipes entire cart
with app.app_context():
    p1 = Product.query.filter_by(product_ref='REF-001').first()
    p2 = Product.query.filter_by(product_ref='REF-002').first()
    p1_ref = p1.product_ref
    cart = Cart.query.filter_by(user_id=customer_kyc_ok_id).first()
    if not cart:
        cart = Cart(user_id=customer_kyc_ok_id, items=[])
        db.session.add(cart)
    cart.items = [
        {'product_id': p1.id, 'qty': 1},
        {'product_id': p2.id, 'qty': 1},
    ]
    db.session.commit()

c_buyer = app.test_client()
login_as(c_buyer, customer_kyc_ok_id)
r_part = c_buyer.post(
    f'/checkout?selected={p1_ref}',
    data={
        'recipient_name': 'KYC Buyer',
        'phone': '09170001111',
        'address_line1': '100 Main St',
        'barangay': 'Bel-Air',
        'city_municipality': 'Makati',
        'province': 'Metro Manila',
        'postal_code': '1209',
        'payment': 'full_pay',
        'agree_terms': '1',
    },
    follow_redirects=False
)
with app.app_context():
    cart = Cart.query.filter_by(user_id=customer_kyc_ok_id).first()
    results['flow_checks']['LOGIC_06_partial_cart_checkout_wipes_unselected'] = {
        'http_status': r_part.status_code,
        'redirect': r_part.headers.get('Location', ''),
        'cart_items_before_count': 2,
        'selected_count': 1,
        'cart_items_after': cart.items if cart else [],
    }

with app.app_context():
    seller_approved = db.session.get(User, seller_approved_id)

    # 7. Check LOGIC-02 & LOGIC-08: Installment order refund pays full order.total when 0 schedules paid & claws back loyalty points
    plan = InstallmentPlan.query.first()
    inst_order = db.session.get(Order, plan.order_id) if plan else Order.query.filter_by(payment_method='installment').first()
    if inst_order:
        if not plan:
            from eacis.services import installment_service as InstSvc
            plan = InstSvc.create_plan(inst_order, months=6, downpayment=Decimal('0.00'))
            db.session.commit()
        cust = db.session.get(User, inst_order.customer_id)
        pts_before = int(cust.loyalty_points or 0)
        paid_scheds = [s for s in (plan.schedules if plan else []) if s.status == 'paid']
        paid_sum = sum(float(s.amount or 0) for s in paid_scheds)
        rrt_inst = ReturnRequest(
            rrt_ref='RRT-AUDIT-INST01',
            order_id=inst_order.id,
            customer_id=inst_order.customer_id,
            reason='defective',
            status='accepted',
            refund_amount=inst_order.total
        )
        db.session.add(rrt_inst)
        db.session.commit()
        ok_ref, msg_ref = RetSvc.process_refund(rrt_inst.id, seller_approved.id)
        db.session.refresh(rrt_inst)
        db.session.refresh(cust)
        if plan:
            db.session.refresh(plan)
        results['flow_checks']['LOGIC_02_08_installment_refund'] = {
            'order_ref': inst_order.order_ref,
            'order_total': float(inst_order.total),
            'actually_paid_before_refund': paid_sum,
            'refunded_amount': float(rrt_inst.refund_amount or 0),
            'plan_status_after_refund': plan.status if plan else None,
            'customer_points_before': pts_before,
            'customer_points_after': int(cust.loyalty_points or 0),
            'process_refund_ok': ok_ref,
            'process_refund_msg': msg_ref,
        }

    # 10. Financial Reconciliation across all seeded orders & installment plans in audit_copy.db
    orders_all = Order.query.all()
    order_math_mismatches = []
    for o in orders_all:
        items_sum = sum((Decimal(str(it.unit_price or 0)) * int(it.quantity or 0)) for it in o.items)
        expected_total = items_sum - Decimal(str(o.discount or 0)) + Decimal(str(o.shipping_fee or 0))
        if abs(expected_total - Decimal(str(o.total or 0))) > Decimal('0.01'):
            order_math_mismatches.append({
                'order_ref': o.order_ref,
                'items_sum': float(items_sum),
                'subtotal_col': float(o.subtotal or 0),
                'discount': float(o.discount or 0),
                'shipping_fee': float(o.shipping_fee or 0),
                'total_col': float(o.total or 0),
                'expected_total': float(expected_total)
            })

    inst_plans = InstallmentPlan.query.all()
    inst_math_mismatches = []
    for pl in inst_plans:
        sched_sum = sum(Decimal(str(s.amount or 0)) for s in pl.schedules)
        fin = Decimal(str(getattr(pl, 'total_financed', None) or getattr(pl, 'principal_amount', 0) or 0))
        if abs(sched_sum - fin) > Decimal('0.05'):
            inst_math_mismatches.append({
                'plan_id': pl.id,
                'order_id': pl.order_id,
                'financed_amount': float(fin),
                'schedules_sum': float(sched_sum),
                'diff': float(sched_sum - fin)
            })

    results['financial_reconciliation'] = {
        'total_orders_checked': len(orders_all),
        'order_math_mismatches': order_math_mismatches,
        'total_installment_plans_checked': len(inst_plans),
        'installment_schedule_mismatches': inst_math_mismatches,
        'voucher_usage_logs_count': VoucherUsageLog.query.count(),
        'orders_with_voucher_count': Order.query.filter(Order.voucher_id.isnot(None)).count(),
    }

out_path = os.path.join(ROOT, 'audit', 'logs', 'dynamic_audit_results.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print("Dynamic audit completed successfully. Saved to", out_path)
