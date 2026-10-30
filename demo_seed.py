"""E-ACIS Demo Seeding Script

Populates realistic, internally consistent demo data for the E-ACIS marketplace demo.
All demo accounts share the uniform password: Demo@12345

Usage:
    python demo_seed.py --reset
"""

import os
import sys
import shutil
import argparse
from datetime import datetime, timedelta
from sqlalchemy import text

# Add repo root to sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from eacis.app import create_app, db
from eacis.reset_and_seed import seed_database
from eacis.models.user import User
from eacis.models.product import Product
from eacis.models.product_image import ProductImage
from eacis.models.order import Order, OrderItem
from eacis.models.installment import InstallmentPlan, InstallmentSchedule
from eacis.models.return_request import ReturnRequest
from eacis.models.refund_transaction import RefundTransaction
from eacis.models.voucher import Voucher
from eacis.models.inquiry_ticket import InquiryTicket
from eacis.models.inquiry_reply import InquiryReply
from eacis.models.review import Review
from eacis.models.product_star import ProductStar
from eacis.models.return_abuse import ReturnAbuseLog
from eacis.models.audit import AuditLog
from eacis.models.cart import Cart

SHARED_PASSWORD = 'Demo@12345'
MERGE_HEAD = '20261030_merge_all_heads'


def backup_database():
    db_path = os.path.join(BASE_DIR, 'instance', 'eacis_dev.db')
    if os.path.exists(db_path):
        bak_path = os.path.join(BASE_DIR, 'instance', 'eacis_dev.db.bak')
        shutil.copyfile(db_path, bak_path)
        print(f"[Backup] Successfully created database backup:\n  {db_path} -> {bak_path}")


def run_demo_seed():
    print("=== [1/5] Executing Core Schema & Foundation Seed ===")
    seed_database()

    app = create_app()
    with app.app_context():
        # Ensure Alembic migration version is stamped to unified head
        try:
            with db.engine.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
                conn.execute(text("DELETE FROM alembic_version"))
                conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{MERGE_HEAD}')"))
            print(f"[Alembic] Stamped head to {MERGE_HEAD}")
        except Exception as e:
            print(f"[Alembic Warning] Could not stamp head: {e}")

        # Update all legacy seeded users with shared password
        for u in User.query.all():
            u.set_password(SHARED_PASSWORD)
            u.is_active = True
        db.session.commit()

        now = datetime.utcnow()

        print("=== [2/5] Seeding Explicit Demo Personas ===")
        # Admin
        admin = User.query.filter_by(email='admin@demo.com').first()
        if not admin:
            admin = User(
                email='admin@demo.com',
                role='admin',
                full_name='System Administrator',
                first_name='System',
                last_name='Admin',
                is_active=True,
                email_verified_at=now
            )
            admin.set_password(SHARED_PASSWORD)
            db.session.add(admin)

        # Sellers
        seller_a = User(
            email='seller.a@demo.com',
            role='seller',
            full_name='Appliance Hub Admin',
            first_name='Hubert',
            last_name='Tan',
            business_name='Appliance Hub Philippines',
            seller_code='SEL-A',
            seller_verification_status='approved',
            business_permit_path='appliance_hub_permit.pdf',
            is_active=True,
            email_verified_at=now,
            city_municipality='Quezon City',
            province='Metro Manila'
        )
        seller_a.set_password(SHARED_PASSWORD)

        seller_b = User(
            email='seller.b@demo.com',
            role='seller',
            full_name='Cool Breeze HVAC Corp',
            first_name='Bernardo',
            last_name='Cruz',
            business_name='Cool Breeze HVAC Corp',
            seller_code='SEL-B',
            seller_verification_status='approved',
            business_permit_path='cool_breeze_permit.pdf',
            is_active=True,
            email_verified_at=now,
            city_municipality='Makati City',
            province='Metro Manila'
        )
        seller_b.set_password(SHARED_PASSWORD)

        seller_c = User(
            email='seller.c@demo.com',
            role='seller',
            full_name='Pending Kitchens Inc',
            first_name='Carlos',
            last_name='Mendoza',
            business_name='Pending Kitchens Inc',
            seller_code='SEL-C',
            seller_verification_status='pending',
            business_permit_path='pending_kitchens_permit.pdf',
            is_active=True,
            email_verified_at=now,
            city_municipality='Pasig City',
            province='Metro Manila'
        )
        seller_c.set_password(SHARED_PASSWORD)

        seller_d = User(
            email='seller.d@demo.com',
            role='seller',
            full_name='Rejected Electro Outlet',
            first_name='Danilo',
            last_name='Reyes',
            business_name='Rejected Electro Outlet',
            seller_code='SEL-D',
            seller_verification_status='rejected',
            is_active=True,
            email_verified_at=now
        )
        seller_d.set_password(SHARED_PASSWORD)

        seller_e = User(
            email='seller.e@demo.com',
            role='seller',
            full_name='Suspended Depot',
            first_name='Eduardo',
            last_name='Lim',
            business_name='Suspended Depot Ltd',
            seller_code='SEL-E',
            seller_verification_status='suspended',
            is_active=True,
            email_verified_at=now
        )
        seller_e.set_password(SHARED_PASSWORD)

        # Customers
        customer1 = User(
            email='customer1@demo.com',
            role='customer',
            full_name='Maria Santos',
            first_name='Maria',
            last_name='Santos',
            address_line1='45 Orchid St, Barangay San Antonio',
            city_municipality='Pasig City',
            province='Metro Manila',
            postal_code='1600',
            phone='09171234567',
            is_active=True,
            email_verified_at=now,
            loyalty_points=500
        )
        customer1.set_password(SHARED_PASSWORD)

        customer2 = User(
            email='customer2@demo.com',
            role='customer',
            full_name='Juan Dela Cruz',
            first_name='Juan',
            last_name='Dela Cruz',
            address_line1='12 Rizal Ave',
            city_municipality='Caloocan City',
            province='Metro Manila',
            postal_code='1400',
            phone='09189876543',
            is_active=True,
            email_verified_at=now,
            loyalty_points=150
        )
        customer2.set_password(SHARED_PASSWORD)

        customer3 = User(
            email='customer3@demo.com',
            role='customer',
            full_name='Elena Gomez',
            first_name='Elena',
            last_name='Gomez',
            address_line1='88 Acacia Lane',
            city_municipality='Mandaluyong City',
            province='Metro Manila',
            postal_code='1550',
            phone='09192233445',
            is_active=True,
            email_verified_at=now,
            loyalty_points=50
        )
        customer3.set_password(SHARED_PASSWORD)

        customer4 = User(
            email='customer4@demo.com',
            role='customer',
            full_name='Carlo Reyes',
            first_name='Carlo',
            last_name='Reyes',
            is_active=True,
            email_verified_at=None  # Gated from completing checkout
        )
        customer4.set_password(SHARED_PASSWORD)

        customer5 = User(
            email='customer5@demo.com',
            role='customer',
            full_name='Rosa Rivera',
            first_name='Rosa',
            last_name='Rivera',
            address_line1='99 Sunset Blvd',
            city_municipality='Taguig City',
            province='Metro Manila',
            postal_code='1630',
            phone='09178889999',
            is_active=True,
            email_verified_at=now,
            loyalty_points=20
        )
        customer5.set_password(SHARED_PASSWORD)

        db.session.add_all([
            seller_a, seller_b, seller_c, seller_d, seller_e,
            customer1, customer2, customer3, customer4, customer5
        ])
        db.session.commit()

        # Seed Return Abuse record for customer5
        abuse_log = ReturnAbuseLog(
            customer_id=customer5.id,
            abuse_score=85,
            flag_reason='Frequent returns with claimed defects',
            is_flagged=True,
            is_restricted=True,
            last_computed=now - timedelta(days=2),
            admin_notes='Flagged by risk engine for excessive refund requests'
        )
        db.session.add(abuse_log)
        db.session.commit()

        print("=== [3/5] Seeding Products for Demo Sellers ===")
        products_data = [
            # Seller A products
            {
                'ref': 'DEMO-PROD-A1',
                'seller_id': seller_a.id,
                'name': 'Samsung 55" Crystal UHD 4K Smart TV',
                'category': 'Entertainment',
                'brand': 'Samsung',
                'model_number': 'UA55CU7000',
                'price': 24999.00,
                'stock': 15,
                'installment_enabled': True,
                'desc': 'Vibrant crystal color comes alive with 4K UHD resolution, Crystal Processor 4K, and Smart Hub.',
                'image': '/static/assets/Featured.png'
            },
            {
                'ref': 'DEMO-PROD-A2',
                'seller_id': seller_a.id,
                'name': 'LG Inverter Smart Front Load Washer 8.5kg',
                'category': 'Laundry',
                'brand': 'LG',
                'model_number': 'FV1408S4W',
                'price': 32490.00,
                'stock': 10,
                'installment_enabled': True,
                'desc': 'AI DD intelligent fabric care with 18% more fabric protection and Steam allergy care.',
                'image': '/static/assets/Featured.png'
            },
            {
                'ref': 'DEMO-PROD-A3',
                'seller_id': seller_a.id,
                'name': 'Panasonic No Frost Two-Door Refrigerator 9.5 cu ft',
                'category': 'Kitchen',
                'brand': 'Panasonic',
                'model_number': 'NR-BP280VD',
                'price': 21499.00,
                'stock': 8,
                'installment_enabled': True,
                'desc': 'Prime Fresh freezing seals flavors and nutrients, with Econavi intelligent sensors.',
                'image': '/static/assets/Featured.png'
            },
            {
                'ref': 'DEMO-PROD-A4',
                'seller_id': seller_a.id,
                'name': 'Philips Digital Airfryer XL 6.2L',
                'category': 'Kitchen',
                'brand': 'Philips',
                'model_number': 'HD9270/90',
                'price': 8990.00,
                'stock': 25,
                'installment_enabled': False,
                'desc': 'Rapid Air technology for healthy frying with up to 90% less fat and touch screen preset menus.',
                'image': '/static/assets/Featured.png'
            },
            # Seller B products (Cool Breeze HVAC)
            {
                'ref': 'DEMO-PROD-B1',
                'seller_id': seller_b.id,
                'name': 'Carrier Aura Inverter Split Type Air Conditioner 1.5HP',
                'category': 'Cooling',
                'brand': 'Carrier',
                'model_number': 'FP-53GCVBE012',
                'price': 34995.00,
                'stock': 12,
                'installment_enabled': True,
                'desc': 'High energy efficiency inverter air conditioner with double clean filter and quiet sleep mode.',
                'image': '/static/assets/Featured.png'
            },
            {
                'ref': 'DEMO-PROD-B2',
                'seller_id': seller_b.id,
                'name': 'Daikin Standard Inverter 1.0HP Split Aircon',
                'category': 'Cooling',
                'brand': 'Daikin',
                'model_number': 'FTKQ25TVM',
                'price': 28500.00,
                'stock': 14,
                'installment_enabled': True,
                'desc': 'Energy-saving cooling with R32 green refrigerant and titanium apatite deodorizing filter.',
                'image': '/static/assets/Featured.png'
            },
            {
                'ref': 'DEMO-PROD-B3',
                'seller_id': seller_b.id,
                'name': 'Xiaomi Smart Air Purifier 4 Pro',
                'category': 'Cooling',
                'brand': 'Xiaomi',
                'model_number': 'AC-M15-SC',
                'price': 11990.00,
                'stock': 18,
                'installment_enabled': False,
                'desc': 'High-efficiency particle filtration captures 99.97% of smoke, pet dander, and allergens.',
                'image': '/static/assets/Featured.png'
            }
        ]

        products_map = {}
        for pdata in products_data:
            p = Product(
                product_ref=pdata['ref'],
                seller_id=pdata['seller_id'],
                name=pdata['name'],
                category=pdata['category'],
                price=pdata['price'],
                compare_price=round(pdata['price'] * 1.15, 2),
                stock=pdata['stock'],
                description=pdata['desc'],
                image_url=pdata['image'],
                warranty_months=12,
                specs={'brand': pdata['brand'], 'model': pdata['model_number']},
                is_active=True,
                installment_enabled=pdata['installment_enabled']
            )
            db.session.add(p)
            db.session.flush()
            products_map[pdata['ref']] = p

            img = ProductImage(
                product_id=p.id,
                filename='Featured.png',
                position=1
            )
            db.session.add(img)

        db.session.commit()

        # Seed reviews & stars
        rev1 = Review(
            product_id=products_map['DEMO-PROD-A1'].id,
            user_id=customer1.id,
            rating=5,
            title='Incredible picture clarity!',
            body='Very bright screen, fast streaming apps, and delivery was spotless. 10/10 recommend!',
            is_approved=True,
            created_at=now - timedelta(days=5)
        )
        rev2 = Review(
            product_id=products_map['DEMO-PROD-B1'].id,
            user_id=customer2.id,
            rating=5,
            title='Cooling is whisper quiet',
            body='Super efficient inverter unit. Lowered our monthly electric bill significantly.',
            is_approved=True,
            created_at=now - timedelta(days=3)
        )
        db.session.add_all([rev1, rev2])
        db.session.add(ProductStar(user_id=customer1.id, product_id=products_map['DEMO-PROD-A1'].id))
        db.session.add(ProductStar(user_id=customer2.id, product_id=products_map['DEMO-PROD-B1'].id))
        db.session.commit()

        print("=== [4/5] Seeding Vouchers & Support Tickets ===")
        vouchers = [
            Voucher(
                voucher_ref='VCH-WELCOME10',
                code='WELCOME10',
                discount_type='percent',
                discount_value=10.0,
                min_order_amount=1000.0,
                max_uses=500,
                uses_count=12,
                per_user_limit=1,
                valid_from=now - timedelta(days=30),
                valid_until=now + timedelta(days=90),
                is_active=True
            ),
            Voucher(
                voucher_ref='VCH-APPHUB500',
                code='APPHUB500',
                discount_type='fixed',
                discount_value=500.0,
                min_order_amount=5000.0,
                max_uses=100,
                uses_count=5,
                per_user_limit=1,
                seller_id=seller_a.id,
                valid_from=now - timedelta(days=10),
                valid_until=now + timedelta(days=60),
                is_active=True
            ),
            Voucher(
                voucher_ref='VCH-LOYAL200',
                code='LOYAL-DEMO',
                discount_type='fixed',
                discount_value=200.0,
                min_order_amount=1500.0,
                max_uses=50,
                uses_count=3,
                per_user_limit=1,
                valid_from=now - timedelta(days=5),
                valid_until=now + timedelta(days=30),
                is_active=True
            )
        ]
        db.session.add_all(vouchers)
        db.session.commit()

        # Support Tickets
        tck1 = InquiryTicket(
            ticket_ref='TCK-DEMO-01',
            customer_id=customer1.id,
            assigned_to=seller_a.id,
            subject='Inquiry about Samsung TV Wall Mount Compatibility',
            description='Does the 55-inch Crystal UHD model include a VESA mounting kit in the standard retail box?',
            priority='medium',
            status='open',
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=2)
        )
        db.session.add(tck1)
        db.session.flush()

        rep1 = InquiryReply(
            ticket_id=tck1.id,
            author_id=seller_a.id,
            body='Hello Maria, the TV has standard 200x200 VESA mounting screw points on the back chassis, but the wall bracket itself is sold separately.',
            is_internal=False,
            created_at=now - timedelta(hours=2)
        )
        db.session.add(rep1)
        db.session.commit()

        print("=== [5/5] Seeding All 7 Order States & Installment Scenarios ===")
        # 1. Delivered Full-Pay Order
        ord_deliv = Order(
            order_ref='ORD-DEMO-DELIV',
            customer_id=customer1.id,
            status='delivered',
            payment_method='full_pay',
            payment_ref='PAY-GCASH-99120',
            subtotal=24999.00,
            discount=0.00,
            shipping_fee=500.00,
            tax=0.00,
            total=25499.00,
            shipping_address={'recipient_name': 'Maria Santos', 'address': '45 Orchid St, Pasig City', 'phone': '09171234567'},
            tracking_number='TRK-DELIV-001',
            created_at=now - timedelta(days=7),
            paid_at=now - timedelta(days=7),
            shipped_at=now - timedelta(days=5),
            delivered_at=now - timedelta(days=3)
        )
        db.session.add(ord_deliv)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_deliv.id, product_id=products_map['DEMO-PROD-A1'].id, quantity=1, unit_price=24999.00, subtotal=24999.00))

        # 2. Multi-Seller Delivered Order (Seller A + Seller B)
        ord_multi = Order(
            order_ref='ORD-DEMO-MULTI',
            customer_id=customer1.id,
            status='delivered',
            payment_method='full_pay',
            payment_ref='PAY-MAYA-44102',
            subtotal=20980.00,  # 8990 (Seller A) + 11990 (Seller B)
            discount=0.00,
            shipping_fee=800.00,
            tax=0.00,
            total=21780.00,
            shipping_address={'recipient_name': 'Maria Santos', 'address': '45 Orchid St, Pasig City', 'phone': '09171234567'},
            tracking_number='TRK-MULTI-778',
            created_at=now - timedelta(days=4),
            paid_at=now - timedelta(days=4),
            shipped_at=now - timedelta(days=3),
            delivered_at=now - timedelta(days=1)
        )
        db.session.add(ord_multi)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_multi.id, product_id=products_map['DEMO-PROD-A4'].id, quantity=1, unit_price=8990.00, subtotal=8990.00))
        db.session.add(OrderItem(order_id=ord_multi.id, product_id=products_map['DEMO-PROD-B3'].id, quantity=1, unit_price=11990.00, subtotal=11990.00))

        # 3. Shipped Order (In transit)
        ord_shipped = Order(
            order_ref='ORD-DEMO-SHIPPED',
            customer_id=customer2.id,
            status='shipped',
            payment_method='full_pay',
            payment_ref='PAY-CARD-8812',
            subtotal=28500.00,
            discount=500.00,
            shipping_fee=600.00,
            tax=0.00,
            total=28600.00,
            shipping_address={'recipient_name': 'Juan Dela Cruz', 'address': '12 Rizal Ave, Caloocan City', 'phone': '09189876543'},
            tracking_number='TRK-EXPRESS-552',
            created_at=now - timedelta(days=2),
            paid_at=now - timedelta(days=2),
            shipped_at=now - timedelta(days=1)
        )
        db.session.add(ord_shipped)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_shipped.id, product_id=products_map['DEMO-PROD-B2'].id, quantity=1, unit_price=28500.00, subtotal=28500.00))

        # 4. Packed Order (Ready to ship)
        ord_packed = Order(
            order_ref='ORD-DEMO-PACKED',
            customer_id=customer3.id,
            status='packed',
            payment_method='full_pay',
            payment_ref='PAY-GCASH-3310',
            subtotal=21499.00,
            discount=0.00,
            shipping_fee=500.00,
            tax=0.00,
            total=21999.00,
            shipping_address={'recipient_name': 'Elena Gomez', 'address': '88 Acacia Lane, Mandaluyong City', 'phone': '09192233445'},
            created_at=now - timedelta(days=1),
            paid_at=now - timedelta(days=1)
        )
        db.session.add(ord_packed)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_packed.id, product_id=products_map['DEMO-PROD-A3'].id, quantity=1, unit_price=21499.00, subtotal=21499.00))

        # 5. Paid Order (Awaiting Seller packing)
        ord_paid = Order(
            order_ref='ORD-DEMO-PAID',
            customer_id=customer2.id,
            status='paid',
            payment_method='full_pay',
            payment_ref='PAY-GCASH-1120',
            subtotal=8990.00,
            discount=0.00,
            shipping_fee=300.00,
            tax=0.00,
            total=9290.00,
            shipping_address={'recipient_name': 'Juan Dela Cruz', 'address': '12 Rizal Ave, Caloocan City', 'phone': '09189876543'},
            created_at=now - timedelta(hours=4),
            paid_at=now - timedelta(hours=4)
        )
        db.session.add(ord_paid)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_paid.id, product_id=products_map['DEMO-PROD-A4'].id, quantity=1, unit_price=8990.00, subtotal=8990.00))

        # 6. Pending Order (Installment waiting for KYC approval)
        ord_pending = Order(
            order_ref='ORD-DEMO-PENDING',
            customer_id=customer2.id,
            status='pending',
            payment_method='installment',
            subtotal=34995.00,
            discount=0.00,
            shipping_fee=800.00,
            tax=0.00,
            total=35795.00,
            shipping_address={'recipient_name': 'Juan Dela Cruz', 'address': '12 Rizal Ave, Caloocan City', 'phone': '09189876543', 'kyc_proof': 'kyc_cust2_id.jpg'},
            notes='Installment 6-months application submitted, awaiting seller KYC verification.',
            created_at=now - timedelta(hours=8)
        )
        db.session.add(ord_pending)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_pending.id, product_id=products_map['DEMO-PROD-B1'].id, quantity=1, unit_price=34995.00, subtotal=34995.00))

        # 7. Cancelled Order
        ord_cancel = Order(
            order_ref='ORD-DEMO-CANCEL',
            customer_id=customer3.id,
            status='cancelled',
            payment_method='full_pay',
            subtotal=8990.00,
            discount=0.00,
            shipping_fee=300.00,
            tax=0.00,
            total=9290.00,
            notes='Cancelled by buyer before payment confirmation.',
            created_at=now - timedelta(days=6)
        )
        db.session.add(ord_cancel)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_cancel.id, product_id=products_map['DEMO-PROD-A4'].id, quantity=1, unit_price=8990.00, subtotal=8990.00))

        # 8. Refunded Order (With ReturnRequest + RefundTransaction)
        ord_refund = Order(
            order_ref='ORD-DEMO-REFUND',
            customer_id=customer5.id,
            status='refunded',
            payment_method='full_pay',
            payment_ref='PAY-CARD-4419',
            subtotal=21499.00,
            discount=0.00,
            shipping_fee=500.00,
            tax=0.00,
            total=21999.00,
            shipping_address={'recipient_name': 'Rosa Rivera', 'address': '99 Sunset Blvd, Taguig City', 'phone': '09178889999'},
            created_at=now - timedelta(days=12),
            paid_at=now - timedelta(days=12),
            delivered_at=now - timedelta(days=9)
        )
        db.session.add(ord_refund)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_refund.id, product_id=products_map['DEMO-PROD-A3'].id, quantity=1, unit_price=21499.00, subtotal=21499.00))

        rrt_refunded = ReturnRequest(
            rrt_ref='RRT-DEMO-REFUNDED',
            order_id=ord_refund.id,
            customer_id=customer5.id,
            reason='defective',
            description='Refrigerator cooling compressor made loud clicking noise and stopped chilling food.',
            status='refunded',
            seller_notes='Confirmed manufacturer defect. Refund approved and issued.',
            refund_amount=21999.00,
            resolved_at=now - timedelta(days=7),
            created_at=now - timedelta(days=8)
        )
        db.session.add(rrt_refunded)
        db.session.flush()

        tx_refund = RefundTransaction(
            refund_ref='RFND-DEMO-001',
            return_request_id=rrt_refunded.id,
            amount=21999.00,
            status='completed',
            method='original_payment_method',
            processed_at=now - timedelta(days=7)
        )
        db.session.add(tx_refund)

        # 9. Installment Order (Delivered, Active on-track plan for Customer 1)
        ord_inst_active = Order(
            order_ref='ORD-DEMO-INST-ACTIVE',
            customer_id=customer1.id,
            status='delivered',
            payment_method='installment',
            subtotal=32490.00,
            discount=0.00,
            shipping_fee=600.00,
            tax=0.00,
            total=33090.00,
            shipping_address={'recipient_name': 'Maria Santos', 'address': '45 Orchid St, Pasig City', 'phone': '09171234567'},
            notes='KYC approved by seller. LG Washer 6-month 0% plan.',
            created_at=now - timedelta(days=65),
            delivered_at=now - timedelta(days=60)
        )
        db.session.add(ord_inst_active)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_inst_active.id, product_id=products_map['DEMO-PROD-A2'].id, quantity=1, unit_price=32490.00, subtotal=32490.00))

        # Downpayment = 6090.00, Financed = 27000.00 over 6 months = 4500.00/mo
        plan_active = InstallmentPlan(
            order_id=ord_inst_active.id,
            months=6,
            monthly_amount=4500.00,
            downpayment=6090.00,
            total_interest=0.00,
            status='active'
        )
        db.session.add(plan_active)
        db.session.flush()

        for i in range(1, 7):
            due = (now - timedelta(days=60) + timedelta(days=30 * i)).date()
            if i <= 2:
                sched = InstallmentSchedule(
                    plan_id=plan_active.id,
                    amount=4500.00,
                    due_date=due,
                    status='paid',
                    paid_at=datetime.combine(due, datetime.min.time()),
                    payment_ref=f'INST-PAY-00{i}'
                )
            else:
                sched = InstallmentSchedule(
                    plan_id=plan_active.id,
                    amount=4500.00,
                    due_date=due,
                    status='pending'
                )
            db.session.add(sched)

        # 10. Installment Order (Overdue plan demo)
        ord_inst_overdue = Order(
            order_ref='ORD-DEMO-INST-OVERDUE',
            customer_id=customer5.id,
            status='delivered',
            payment_method='installment',
            subtotal=24999.00,
            discount=0.00,
            shipping_fee=500.00,
            tax=0.00,
            total=25499.00,
            notes='Overdue demo plan.',
            created_at=now - timedelta(days=90),
            delivered_at=now - timedelta(days=85)
        )
        db.session.add(ord_inst_overdue)
        db.session.flush()
        db.session.add(OrderItem(order_id=ord_inst_overdue.id, product_id=products_map['DEMO-PROD-A1'].id, quantity=1, unit_price=24999.00, subtotal=24999.00))

        plan_overdue = InstallmentPlan(
            order_id=ord_inst_overdue.id,
            months=6,
            monthly_amount=3500.00,
            downpayment=4499.00,
            total_interest=0.00,
            status='active'
        )
        db.session.add(plan_overdue)
        db.session.flush()

        for i in range(1, 7):
            due = (now - timedelta(days=85) + timedelta(days=30 * i)).date()
            if i == 1:
                sched = InstallmentSchedule(plan_id=plan_overdue.id, amount=3500.00, due_date=due, status='paid', paid_at=now - timedelta(days=55))
            elif i == 2:
                sched = InstallmentSchedule(plan_id=plan_overdue.id, amount=3500.00, due_date=due, status='past_due')
            else:
                sched = InstallmentSchedule(plan_id=plan_overdue.id, amount=3500.00, due_date=due, status='pending')
            db.session.add(sched)

        # Pending and Accepted Return Requests for Seller A
        rrt_pending = ReturnRequest(
            rrt_ref='RRT-DEMO-PENDING',
            order_id=ord_deliv.id,
            customer_id=customer1.id,
            reason='accessories_missing',
            description='Remote control and standard wall spacers were missing from the package.',
            status='pending',
            created_at=now - timedelta(hours=14)
        )
        db.session.add(rrt_pending)

        db.session.commit()

        # Audit logs for demo
        audit1 = AuditLog(
            actor_id=seller_a.id,
            actor_name='Hubert Tan',
            role='seller',
            action='LOGIN_SUCCESS',
            module='auth',
            target_ref=seller_a.email,
            meta={'client': 'Chrome/Win10'},
            ip_address='127.0.0.1',
            created_at=now - timedelta(hours=2)
        )
        audit2 = AuditLog(
            actor_id=admin.id,
            actor_name='System Admin',
            role='admin',
            action='SELLER_VERIFICATION_APPROVE',
            module='admin',
            target_ref=seller_b.email,
            meta={'notes': 'Permit verified'},
            ip_address='127.0.0.1',
            created_at=now - timedelta(days=1)
        )
        db.session.add_all([audit1, audit2])
        db.session.commit()

        print("\n=== Demo Database Reset & Seeding Completed Successfully ===")
        print("=" * 70)
        print("DEMO CREDENTIALS (Password for ALL: Demo@12345):")
        print("  Role       Email                  Persona / Scenario")
        print("  ---------- ---------------------- ----------------------------------")
        print("  Admin:     admin@demo.com         Full Backoffice & KYC Approvals")
        print("  Seller A:  seller.a@demo.com      Appliance Hub (Approved, Orders)")
        print("  Seller B:  seller.b@demo.com      Cool Breeze HVAC (Multi-Seller)")
        print("  Seller C:  seller.c@demo.com      Pending Kitchens (Pending)")
        print("  Seller D:  seller.d@demo.com      Rejected Electro (Rejected)")
        print("  Seller E:  seller.e@demo.com      Suspended Depot (Suspended 403)")
        print("  Customer 1: customer1@demo.com    Maria Santos (KYC Approved, Inst)")
        print("  Customer 2: customer2@demo.com    Juan Dela Cruz (KYC Pending)")
        print("  Customer 3: customer3@demo.com    Elena Gomez (Live KYC Test)")
        print("  Customer 4: customer4@demo.com    Carlo Reyes (Unverified Customer)")
        print("  Customer 5: customer5@demo.com    Rosa Rivera (Abuse Flagged)")
        print("=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Seed E-ACIS realistic demo database.")
    parser.add_argument('--reset', action='store_true', help="Reset and recreate database before seeding")
    args = parser.parse_args()

    backup_database()
    run_demo_seed()
