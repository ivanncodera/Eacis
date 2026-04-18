#!/usr/bin/env python3
"""Smoke test: create a delivered order for a temp user and exercise review/star flows."""
import sys
import os
import uuid
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eacis.app import create_app


def main():
    app = create_app()
    with app.app_context():
        try:
            from eacis.extensions import db
            from eacis.models.user import User
            from eacis.models.product import Product
            from eacis.models.order import Order, OrderItem
        except Exception:
            from extensions import db
            from models.user import User
            from models.product import Product
            from models.order import Order, OrderItem

        # create unique test data
        email = f"test.reviewer+{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, role='customer', full_name='Test Reviewer')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        prod_ref = f"TEST-PROD-{uuid.uuid4().hex[:8]}"
        product = Product(product_ref=prod_ref, name='Test Product for Reviews', price=1000.00, stock=10)
        db.session.add(product)
        db.session.commit()

        order = Order(order_ref=f'ORD-{uuid.uuid4().hex[:8]}', customer_id=user.id, status='delivered', subtotal=1000, total=1000, payment_method='full_pay', delivered_at=datetime.utcnow())
        db.session.add(order)
        db.session.commit()

        item = OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price=1000, subtotal=1000)
        db.session.add(item)
        db.session.commit()

        try:
            from eacis.services.review_service import has_user_received_product, create_or_update_review, toggle_star
        except Exception:
            from services.review_service import has_user_received_product, create_or_update_review, toggle_star

        print('has_user_received_product:', has_user_received_product(user.id, product.id))

        rv, err = create_or_update_review(user.id, product.id, 5, title='Great', body='Works well', is_anonymous=False, require_purchase=True)
        print('create_or_update_review ->', 'ok' if rv and not err else f'error: {err}')

        res, err = toggle_star(user.id, product.id, require_purchase=True)
        print('toggle_star ->', res, err)

        # cleanup is intentionally omitted so records remain for manual inspection


if __name__ == '__main__':
    main()
