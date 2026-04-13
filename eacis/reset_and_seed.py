import os
import sys
from datetime import datetime
from decimal import Decimal

# Ensure we're in the right path to import eacis
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.user import User
from eacis.models.product import Product

def seed_database():
    app = create_app()
    with app.app_context():
        print("--- Resetting Database ---")
        db.drop_all()
        db.create_all()
        print("Database structure recreated.")

        # 1. Create Users
        print("--- Seeding Users ---")
        
        # Admin
        admin = User(
            email='admin@eacis.com',
            role='admin',
            full_name='System Administrator',
            first_name='Admin',
            last_name='User',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # Verified Seller
        seller_v = User(
            email='seller@verified.com',
            role='seller',
            business_name='Extreme Appliances PH',
            first_name='Juan',
            last_name='Verified',
            seller_verification_status='approved',
            seller_code='SELLER01',
            is_active=True
        )
        seller_v.set_password('seller123')
        db.session.add(seller_v)

        # Unverified Seller
        seller_u = User(
            email='seller@pending.com',
            role='seller',
            business_name='New Start Shop',
            first_name='Maria',
            last_name='Wait',
            seller_verification_status='pending',
            seller_code='SELLER02',
            is_active=True
        )
        seller_u.set_password('seller123')
        db.session.add(seller_u)

        # Customer
        customer = User(
            email='customer@demo.com',
            role='customer',
            full_name='Demo Customer',
            first_name='Demo',
            last_name='User',
            address_line1='123 Digital Ave.',
            barangay='San Lorenzo',
            city_municipality='Makati',
            province='Metro Manila',
            postal_code='1200',
            is_active=True,
            loyalty_points=500
        )
        customer.set_password('customer123')
        db.session.add(customer)

        db.session.commit()
        print("Users created successfully.")

        # 2. Create Products for Verified Seller
        print("--- Seeding Products ---")
        
        products_to_seed = [
            {
                'name': '2-Door Smart Refrigerator',
                'ref': 'REF-001',
                'price': Decimal('32500.00'),
                'stock': 15,
                'category': 'Refrigeration',
                'image': '2-door-refrigirator.webp',
                'desc': 'Energy-efficient 2-door refrigerator with smart cooling technology.'
            },
            {
                'name': 'Split-Type Inverter Aircon',
                'ref': 'AC-001',
                'price': Decimal('28999.00'),
                'stock': 10,
                'category': 'Cooling',
                'image': 'split-type-aircon.webp',
                'desc': '1.5HP Split-type inverter air conditioner with fast cooling mode.'
            },
            {
                'name': 'Front Load Washing Machine',
                'ref': 'WM-001',
                'price': Decimal('24500.00'),
                'stock': 8,
                'category': 'Laundry',
                'image': 'frontload-washing-machine.jpg',
                'desc': 'High-performance front load washing machine with steam wash.'
            },
            {
                'name': '4-Burner Gas Range',
                'ref': 'GR-001',
                'price': Decimal('18750.00'),
                'stock': 5,
                'category': 'Cooking',
                'image': 'gas-range-with-oven-4-burners.webp',
                'desc': 'Professional gas range with 4 burners and integrated oven.'
            },
            {
                'name': '4K UHD Smart TV 55"',
                'ref': 'TV-001',
                'price': Decimal('42999.00'),
                'stock': 20,
                'category': 'Entertainment',
                'image': 'smart-tv.jfif',
                'desc': 'Stunning 4K resolution with built-in streaming apps and HDR.'
            },
            {
                'name': 'Digital Air Fryer',
                'ref': 'AF-001',
                'price': Decimal('4500.00'),
                'stock': 50,
                'category': 'Cooking',
                'image': 'air-fryer.jfif',
                'desc': 'Healthy cooking with little to no oil. Large capacity basket.'
            },
            {
                'name': 'Stand Mixer Pro',
                'ref': 'MX-001',
                'price': Decimal('8900.00'),
                'stock': 12,
                'category': 'Appliances',
                'image': 'stand-mixer.jfif',
                'desc': 'Heavy-duty stand mixer for professional baking and dough mixing.'
            },
            {
                'name': 'Robot Vacuum Cleaner',
                'ref': 'VAC-001',
                'price': Decimal('12500.00'),
                'stock': 15,
                'category': 'Cleaning',
                'image': 'robot-vacuum.jfif',
                'desc': 'Smart navigation robot vacuum with scheduled cleaning features.'
            }
        ]

        for p_data in products_to_seed:
            prod = Product(
                product_ref=p_data['ref'],
                seller_id=seller_v.id,
                name=p_data['name'],
                category=p_data['category'],
                description=p_data['desc'],
                price=p_data['price'],
                compare_price=p_data['price'] * Decimal('1.2'),
                stock=p_data['stock'],
                image_url=f"/static/assets/products/{p_data['image']}",
                installment_enabled=True,
                is_active=True,
                weight_kg=Decimal('10.0')
            )
            db.session.add(prod)

        db.session.commit()
        print(f"{len(products_to_seed)} products seeded to verified seller.")
        
        print("\n--- DEMO DATA READY ---")
        print(f"Customer: customer@demo.com / customer123")
        print(f"Seller (Verified): seller@verified.com / seller123")
        print(f"Seller (Pending): seller@pending.com / seller123")
        print(f"Admin: admin@eacis.com / admin123")
        print("------------------------")

if __name__ == "__main__":
    seed_database()
