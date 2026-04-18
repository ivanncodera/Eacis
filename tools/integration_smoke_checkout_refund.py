#!/usr/bin/env python3
import os
import sys
import pathlib
from datetime import datetime, timedelta

pkg_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_root))

from eacis.app import create_app

app = create_app()

with app.app_context():
    # imports
    try:
        from eacis.extensions import db
    except Exception:
        from extensions import db

    try:
        from eacis.models.user import User
        from eacis.models.product import Product
        from eacis.models.order import Order, OrderItem
        from eacis.models.cart import Cart
        from eacis.services import return_service as RetSvc
        from eacis.models.refund_transaction import RefundTransaction
    except Exception:
        from models.user import User
        from models.product import Product
        from models.order import Order, OrderItem
        from models.cart import Cart
        from services import return_service as RetSvc
        from models.refund_transaction import RefundTransaction

    # ensure schema exists
    db.create_all()

    # create seller
    seller_email = 'int_seller@example.com'
    seller = User.query.filter_by(email=seller_email).first()
    if not seller:
        seller = User(email=seller_email, role='seller', full_name='Integration Seller')
        seller.set_password('password')
        seller.seller_verification_status = 'approved'
        db.session.add(seller)
        db.session.commit()

    # create customer
    customer_email = 'int_customer@example.com'
    customer = User.query.filter_by(email=customer_email).first()
    if not customer:
        customer = User(email=customer_email, role='customer', full_name='Integration Customer')
        customer.set_password('password')
        db.session.add(customer)
        db.session.commit()

    # create product
    prod_ref = 'INT-PROD-001'
    product = Product.query.filter_by(product_ref=prod_ref).first()
    if not product:
        product = Product(product_ref=prod_ref, seller_id=seller.id, name='Integration Test Product', price=100.00, stock=5)
        db.session.add(product)
        db.session.commit()
    else:
        product.stock = max(int(product.stock or 0), 5)
        db.session.commit()

    # disable CSRF for test client
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    # Log in as customer
    with client.session_transaction() as sess:
        sess['_user_id'] = str(customer.id)
        sess['_fresh'] = True

    # Add product to cart
    resp = client.post('/cart', data={'action': 'add', 'product_ref': prod_ref, 'qty': '1', 'next': '/checkout'}, follow_redirects=True)
    print('ADD_TO_CART_STATUS', resp.status_code)

    # Perform checkout
    checkout_data = {
        'action': 'place_order',
        'agree_terms': '1',
        'payment': 'full_pay',
        'recipient_name': customer.computed_full_name or customer.full_name,
        'address_line1': '123 Integration St',
        'postal_code': '1000',
        'phone': '09171234567',
    }
    resp = client.post('/checkout', data=checkout_data, follow_redirects=True)
    print('CHECKOUT_STATUS', resp.status_code)

    # Find the latest order for the customer
    order = Order.query.filter_by(customer_id=customer.id).order_by(Order.id.desc()).first()
    if not order:
        print('ERROR: Order not created')
        sys.exit(1)

    print('ORDER_CREATED', order.order_ref, 'STATUS', order.status)

    # Mark order as delivered for return eligibility
    order.status = 'delivered'
    order.delivered_at = datetime.utcnow() - timedelta(days=1)
    db.session.commit()
    print('ORDER_MARKED_DELIVERED')

    # Create a return request programmatically
    # Ensure ReturnRequest instances expose `reason_category` (backwards-compat shim)
    try:
        from eacis.models.return_request import ReturnRequest
    except Exception:
        from models.return_request import ReturnRequest
    if not hasattr(ReturnRequest, 'reason_category'):
        # Add a simple class-level fallback so instances have the attribute and can be assigned.
        ReturnRequest.reason_category = ''

    rrt, msg = RetSvc.create_return_request(customer.id, order.id, 'DEFECTIVE', 'Integration test defect')
    print('CREATE_RETURN_REQUEST', bool(rrt), msg)
    if not rrt:
        print('Return request creation failed; aborting.')
        sys.exit(1)

    # Process refund as seller
    ok, rmsg = RetSvc.process_refund(rrt.id, seller_id=seller.id)
    print('PROCESS_REFUND', ok, rmsg)

    # Verify refund transaction exists
    refunds = RefundTransaction.query.filter_by(return_request_id=rrt.id).all()
    print('REFUND_ROWS', len(refunds))

    # Verify product stock (should be restored by restock)
    refreshed = Product.query.get(product.id)
    print('PRODUCT_STOCK_AFTER_REFUND', refreshed.stock)

    print('INTEGRATION_SMOKE_DONE')
