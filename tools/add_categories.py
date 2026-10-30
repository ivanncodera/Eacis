#!/usr/bin/env python3
"""Create placeholder products so new categories exist in the system.

This script creates one minimal product per category (using an approved seller)
so the category strings show up in the storefront category lists which are
derived from distinct `Product.category` values.

Run from the repository root with the virtualenv activated:

    python tools/add_categories.py

Be cautious: this creates Product rows. Remove them later from admin if needed.
"""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
import secrets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.product import Product
from eacis.models.user import User


def get_categories_from_reference():
    # Subcategory list derived from the user's reference (roughly 50+ items)
    return [
        'Refrigerators','Microwaves','Ovens','Rice Cookers','Blenders','Air Fryers',
        'Air Conditioners','Electric Fans','Air Coolers','Air Purifiers','Humidifiers','Dehumidifiers',
        'Washing Machines','Dryers','Vacuum Cleaners','Steam Cleaners','Carpet Cleaners','Floor Polishers',
        'Televisions','Sound Systems','Speakers','Gaming Consoles','Projectors','Streaming Devices',
        'Hair Dryers','Hair Straighteners','Hair Curlers','Electric Shavers','Beard Trimmers','Facial Steamers',
        'Electric Irons','Garment Steamers','Water Dispensers','Water Purifiers','Sewing Machines','Massage Chairs',
        'Generators','Pressure Washers','Electric Grills','Ice Makers','Wine Coolers','Power Tools',
        'Smart Refrigerators','Smart TVs','Smart Washing Machines','Robot Vacuums','Smart Air Conditioners','Smart Lighting Systems',
        'Printers','Scanners',
        'Mobile Devices','Tablets','Laptops & Computers','Computer Accessories','Wearable Technology'
    ]


def ensure_seller():
    seller = User.query.filter_by(role='seller', seller_verification_status='approved', is_active=True).first()
    if seller:
        return seller
    # Create a lightweight seller account used only for these placeholder products
    s = User(
        email='category-seeder@local',
        role='seller',
        business_name='Category Seeder',
        first_name='Category',
        last_name='Seeder',
        seller_verification_status='approved',
        is_active=True,
    )
    try:
        s.set_password('seeder123')
    except Exception:
        pass
    db.session.add(s)
    db.session.commit()
    return s


def main():
    app = create_app()
    with app.app_context():
        cats = get_categories_from_reference()
        existing = set(r[0] for r in db.session.query(Product.category).distinct().all() if r[0])
        seller = ensure_seller()

        created = []
        for name in cats:
            if name in existing:
                continue
            ref = f"CAT-{secrets.token_hex(4).upper()}"
            p = Product(
                product_ref=ref,
                seller_id=seller.id,
                name=f"[CATEGORY] {name} (placeholder)",
                category=name,
                description=f"Placeholder product to register category '{name}'",
                price=Decimal('1.00'),
                compare_price=Decimal('1.15'),
                stock=0,
                installment_enabled=False,
                is_active=True,
                weight_kg=Decimal('1.0'),
                image_url='/static/assets/products/demo-placeholder.jfif',
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(p)
            try:
                db.session.commit()
                created.append(name)
                existing.add(name)
                print('Created category placeholder:', name)
            except Exception as e:
                db.session.rollback()
                print('Skipped', name, '->', str(e))

        print('\nSummary:')
        print('Existing categories kept:', len(existing) - len(created))
        print('New categories created:', len(created))


if __name__ == '__main__':
    main()
