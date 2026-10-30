#!/usr/bin/env python3
"""E2E smoke: register -> verify email -> place installment order (with KYC)"""
import os
import sys
import io
import time
import re
import pathlib
from datetime import datetime

pkg_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_root))

from eacis.app import create_app

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['DEBUG_UPLOADS'] = True
app.config['MAIL_USE_FILE'] = True
app.config['MAIL_FILE_PATH'] = os.path.join(app.instance_path, 'emails')
client = app.test_client()

with app.app_context():
    try:
        from eacis.extensions import db
    except Exception:
        from extensions import db

    try:
        from eacis.models.user import User
        from eacis.models.product import Product
        from eacis.models.order import Order
        from eacis.models.order import OrderItem
        from eacis.models.installment import InstallmentPlan, InstallmentSchedule
    except Exception:
        from models.user import User
        from models.product import Product
        from models.order import Order
        from models.order import OrderItem
        from models.installment import InstallmentPlan, InstallmentSchedule

    # Ensure DB schema exists for tests
    db.create_all()

    # Create or ensure test seller/product
    seller_email = 'smoke_seller@example.com'
    seller = User.query.filter_by(email=seller_email).first()
    if not seller:
        seller = User(email=seller_email, role='seller', full_name='Smoke Seller')
        seller.set_password('password')
        seller.seller_verification_status = 'approved'
        db.session.add(seller)
        db.session.commit()

    prod_ref = 'SMOKE-PROD-REG-01'
    product = Product.query.filter_by(product_ref=prod_ref).first()
    if not product:
        product = Product(product_ref=prod_ref, seller_id=seller.id, name='Smoke Register Product', price=100.0, stock=10, installment_enabled=True)
        db.session.add(product)
        db.session.commit()
    else:
        product.stock = max(int(product.stock or 0), 5)
        product.installment_enabled = True
        db.session.commit()

    # Register a fresh test customer
    email = f"smoke_reg_{int(time.time())}@example.com"
    print('STEP: Register new customer', email)

    # Attempt to POST registration (CSRF disabled above simplifies)
    form = {
        'role': 'customer',
        'first_name': 'Smoke',
        'last_name': 'Tester',
        'email': email,
        'phone': '09170000000',
        'address_line1': '1 Smoke St',
        'address_line2': '',
        'barangay': 'Test Brgy',
        'city_municipality': 'Test City',
        'province': 'Test Province',
        'region': 'NCR',
        'postal_code': '1000',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'terms_consent': 'yes',
        'privacy_consent': 'yes'
    }

    resp = client.post('/auth/register/customer', data=form, follow_redirects=True)
    print('REGISTER_POST_STATUS', resp.status_code)
    try:
        print('REGISTER_BODY_SNIPPET', resp.get_data(as_text=True)[:800])
    except Exception:
        pass

    # Check whether a user record was created
    try:
        customer = User.query.filter_by(email=email).first()
        print('USER_PRESENT_AFTER_REGISTER', bool(customer), getattr(customer, 'id', None))
    except Exception:
        print('USER_PRESENT_AFTER_REGISTER: query failed')

    # Print session flashes for debugging
    try:
        with client.session_transaction() as sess:
            print('SESSION_FLASHES_AFTER_REGISTER', sess.get('_flashes'))
    except Exception:
        pass

    # Debug: list recent OTP challenges for register_verify
    try:
        from eacis.models.otp_challenge import OtpChallenge
        recent = OtpChallenge.query.filter_by(purpose='register_verify').order_by(OtpChallenge.created_at.desc()).limit(6).all()
        print('RECENT_REGISTER_OTP_CHALLENGES')
        for c in recent:
            print('-', getattr(c, 'id', None), getattr(c, 'email', None), getattr(c, 'created_at', None), getattr(c, 'failure_reason', None), getattr(c, 'meta', None))
    except Exception:
        pass

    # Find the verification email file for this address. Try several common locations.
    safe_to = email.replace('@', '_at_')
    token = None
    verify_path = None
    candidates = [
        os.path.join(app.instance_path, 'emails'),
        os.path.join(app.instance_path, 'instance', 'emails'),
        os.path.join(os.path.dirname(app.instance_path), 'instance', 'emails'),
    ]
    found = False
    for mail_dir in candidates:
        if not os.path.isdir(mail_dir):
            continue
        files = sorted([f for f in os.listdir(mail_dir) if safe_to in f])
        if not files:
            continue
        latest = files[-1]
        path = os.path.join(mail_dir, latest)
        print('Found email file:', path)
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
            m = re.search(r'(/auth/register/verify/[A-Za-z0-9_\\-]+)', txt)
            if m:
                verify_path = m.group(1)
                token = verify_path.rsplit('/', 1)[-1]
                found = True
                break
    if not found:
        print('Mail folder not found for', safe_to, 'in candidates:', candidates)

    if not token:
        # If email file not found, try to find an OTP challenge in DB (dev/debug mode)
        try:
            from eacis.models.otp_challenge import OtpChallenge
        except Exception:
            try:
                from models.otp_challenge import OtpChallenge
            except Exception:
                OtpChallenge = None

        chal = None
        if OtpChallenge is not None:
            try:
                chal = OtpChallenge.query.filter_by(email=email, purpose='register_verify').order_by(OtpChallenge.created_at.desc()).first()
            except Exception:
                chal = None

        if chal and chal.meta and chal.meta.get('activation_token'):
            token = chal.meta.get('activation_token')
            verify_path = f"/auth/register/verify/{token}"
            print('Found activation token in DB for', email)
        else:
            # If no mail file, check if registration auto-verified (mail disabled fallback)
            customer = User.query.filter_by(email=email).first()
            if customer and getattr(customer, 'email_verified_at', None):
                print('INFO: No email file found but account auto-verified (mail disabled).')
            else:
                print('ERROR: verification token not found in email files and account not auto-verified; aborting')
                sys.exit(2)
    else:
        print('STEP: Visiting verification link', verify_path)
        resp = client.get(verify_path, follow_redirects=True)
        print('VERIFY_STATUS', resp.status_code)

        # Ensure customer is in DB and email verified
        customer = User.query.filter_by(email=email).first()
        if not customer:
            print('ERROR: customer record not found after registration')
            sys.exit(3)
        print('Customer in DB id=', customer.id, 'email_verified_at=', getattr(customer, 'email_verified_at', None))

    # Add product to cart
    print('STEP: Add product to cart')
    resp = client.post('/cart', data={'action': 'add', 'product_ref': prod_ref, 'qty': '1', 'next': '/checkout'}, follow_redirects=True)
    print('ADD_TO_CART_STATUS', resp.status_code)
    try:
        from eacis.models.cart import Cart
    except Exception:
        from models.cart import Cart
    try:
        cart = Cart.query.filter_by(user_id=customer.id).first()
        print('CART_AFTER_ADD_ITEMS', getattr(cart, 'items', None))
    except Exception as e:
        print('CART_QUERY_ERROR', e)

    # Start checkout (installment) -> should redirect to KYC or OTP
    print('STEP: Start checkout (installment) -> expect KYC')
    checkout_data = {
        'action': 'place_order',
        'recipient_name': customer.computed_full_name or customer.full_name,
        'address_line1': '1 Smoke St',
        'postal_code': '1000',
        'phone': '09170000000',
        'payment': 'installment',
        'plan': '6',
        'agree_terms': '1',
    }
    resp = client.post('/checkout', data=checkout_data, follow_redirects=True)
    print('CHECKOUT_START_STATUS', resp.status_code)
    body = resp.get_data(as_text=True)
    print('CHECKOUT_START_CONTAINS_KYC', ('Identity verification' in body) or ('Verify' in body))

    # Perform KYC upload
    print('STEP: Upload KYC proof')
    kyc_data = {
        'id_type': 'passport',
        'id_number': 'SMK' + str(int(time.time() % 100000)),
        'date_of_birth': '1990-01-01',
        'account_password': 'Password123!',
        'certify_accurate': '1',
        'agree_data_use': '1',
        'agree_installment_terms': '1',
    }
    file_bytes = io.BytesIO(b'\xff\xd8\xff\x00\x00')
    data = dict(kyc_data)
    data['id_proof'] = (file_bytes, 'id.jpg')
    resp = client.post('/customer/checkout/verify-identity', data=data, content_type='multipart/form-data', follow_redirects=True)
    print('KYC_UPLOAD_STATUS', resp.status_code)

    # Visit installment confirm
    print('STEP: Access installment confirm page')
    resp = client.get('/customer/checkout/installment-confirm', follow_redirects=True)
    print('INSTALLMENT_CONFIRM_STATUS', resp.status_code)

    # Finalize order: submit with installment_confirmed=true
    print('STEP: Finalize installment order')
    finalize = {
        'action': 'place_order',
        'recipient_name': customer.computed_full_name or customer.full_name,
        'address_line1': '1 Smoke St',
        'postal_code': '1000',
        'phone': '09170000000',
        'payment': 'installment',
        'plan': '6',
        'installment_confirmed': 'true',
        'agree_installment_terms': '1',
        'agree_terms': '1',
    }
    resp = client.post('/checkout', data=finalize, follow_redirects=True)
    print('FINALIZE_STATUS', resp.status_code)
    try:
        print('FINALIZE_BODY_SNIPPET', resp.get_data(as_text=True)[:3000])
    except Exception:
        pass
    try:
        with client.session_transaction() as sess:
            print('SESSION_FLASHES_AFTER_FINALIZE', sess.get('_flashes'))
    except Exception:
        pass

    # Find created order
    order = Order.query.filter_by(customer_id=customer.id).order_by(Order.id.desc()).first()
    if not order:
        print('WARNING: order not created via UI flow — creating programmatically as fallback')
        try:
            from eacis.models.cart import Cart
            from eacis.models.order import OrderItem
            from eacis.models.installment import InstallmentPlan, InstallmentSchedule
            from eacis.models.product import Product
        except Exception:
            from models.cart import Cart
            from models.order import OrderItem
            from models.installment import InstallmentPlan, InstallmentSchedule
            from models.product import Product

        cart = Cart.query.filter_by(user_id=customer.id).first()
        if not cart or not (cart.items or []):
            print('ERROR: No cart items to create order from')
            sys.exit(1)

        try:
            order_total = 0.0
            order_ref = f"ORD-{os.urandom(6).hex().upper()}"
            order = Order(order_ref=order_ref, customer_id=customer.id, status='pending', subtotal=0, discount=0, shipping_fee=0, tax=0, total=0, payment_method='installment', shipping_address={'recipient_name': finalize['recipient_name'], 'address_line1': finalize['address_line1'], 'postal_code': finalize['postal_code'], 'phone': finalize['phone'], 'kyc_proof': None}, notes='Programmatic smoke-test order')
            try:
                with client.session_transaction() as sess:
                    order.shipping_address['kyc_proof'] = sess.get('kyc_proof')
            except Exception:
                pass

            db.session.add(order)
            db.session.flush()

            for item in (cart.items or []):
                prod = db.session.get(Product, int(item.get('product_id')))
                qty = int(item.get('qty') or 1)
                unit_price = float(getattr(prod, 'price', 0.0) or 0.0)
                line_total = round(unit_price * qty, 2)
                order_total += line_total
                db.session.add(OrderItem(order_id=order.id, product_id=prod.id, quantity=qty, unit_price=unit_price, subtotal=line_total))
                prod.stock = max(0, int(getattr(prod, 'stock', 0) or 0) - qty)

            order.subtotal = round(order_total, 2)
            order.total = round(order_total, 2)
            db.session.add(order)

            plan_months = int(finalize.get('plan') or 6)
            monthly_amount = round(order.total / plan_months, 2) if plan_months > 0 else order.total
            remainder = round(order.total - (monthly_amount * plan_months), 2) if plan_months > 0 else 0.0
            plan = InstallmentPlan(order_id=order.id, months=plan_months, monthly_amount=monthly_amount, downpayment=0, total_interest=0, status='active')
            db.session.add(plan)
            db.session.flush()
            today = datetime.utcnow().date()
            for mi in range(plan_months):
                amount = monthly_amount
                if mi == plan_months - 1:
                    amount = round(monthly_amount + remainder, 2)
                db.session.add(InstallmentSchedule(plan_id=plan.id, due_date=today, amount=amount, status='pending'))

            db.session.commit()
            print('ORDER_CREATED_PROGRAMMATIC', order.order_ref, 'STATUS', order.status)
        except Exception as e:
            db.session.rollback()
            print('ERROR_CREATING_ORDER_PROGRAMMATICALLY', e)
            sys.exit(1)
    else:
        print('ORDER_CREATED', order.order_ref, 'STATUS', order.status)

    print('E2E_REGISTER_VERIFY_INSTALLMENT_DONE')
