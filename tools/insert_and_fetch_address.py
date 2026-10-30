#!/usr/bin/env python
"""Insert an address directly into DB for the dev user and fetch the addresses API as that user."""
import sys
import pathlib
from datetime import datetime

project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.user import User
from eacis.models.address import Address


def main():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email='customer@example.com').first()
        if not user:
            user = User(email='customer@example.com', role='customer', full_name='Dev Customer')
            user.set_password('password')
            user.email_verified_at = datetime.utcnow()
            db.session.add(user)
            db.session.commit()
        # create address directly
        a = Address(user_id=user.id, label='SmokeTest', recipient_name='Dev Customer', phone='9123456789', address_line1='Smoke Street 1', barangay='Smoke Brgy', city_municipality='Test City', province='Test Province', postal_code='1000', is_default=True, lat=14.6, lng=120.98)
        db.session.add(a)
        db.session.commit()
        print('Inserted address id', a.id)

        client = app.test_client()
        # set session to simulate login
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        rv = client.get('/customer/addresses/api')
        print('api status', rv.status_code)
        try:
            print('api json count', len(rv.get_json() or []))
            print(rv.get_json())
        except Exception:
            print(rv.get_data(as_text=True)[:800])
        # fetch checkout page to confirm saved address is rendered
        # Ensure there's a product and cart for current_user so checkout shows
        try:
            from eacis.models.product import Product
            from eacis.models.cart import Cart
        except Exception:
            from models.product import Product
            from models.cart import Cart
        # create a test product if none exists
        prod = db.session.query(Product).filter_by(product_ref='SMOKE-PROD').first()
        if not prod:
            prod = Product(product_ref='SMOKE-PROD', name='Smoke Test Product', price=100.00, stock=10, seller_id=1)
            db.session.add(prod)
            db.session.commit()
        # create or update cart for user
        cart = Cart.query.filter_by(user_id=user.id).first()
        if not cart:
            cart = Cart(user_id=user.id, items=[{'product_id': prod.id, 'qty': 1}])
            db.session.add(cart)
            db.session.commit()
        else:
            cart.items = [{'product_id': prod.id, 'qty': 1}]
            db.session.commit()

        rv2 = client.get('/checkout')
        print('/checkout status', rv2.status_code, 'Location:', rv2.headers.get('Location'))
        rv3 = client.get('/checkout', follow_redirects=True)
        html = rv3.get_data(as_text=True)
        found = 'SmokeTest' in html or 'Smoke Street 1' in html
        print('/checkout follow status', rv3.status_code, 'contains saved address?', found)


if __name__ == '__main__':
    main()
