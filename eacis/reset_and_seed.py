import os
import sys
from datetime import datetime
from decimal import Decimal
from sqlalchemy import text

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
        # Some MySQL setups enforce foreign key checks that prevent DROP TABLE ordering.
        # Temporarily disable FK checks for the drop/create cycle when using MySQL.
        try:
            dialect = db.engine.dialect.name
        except Exception:
            dialect = None

        if dialect in ('mysql', 'mariadb'):
            with db.engine.begin() as conn:
                conn.execute(text('SET FOREIGN_KEY_CHECKS=0'))

        db.drop_all()

        if dialect in ('mysql', 'mariadb'):
            # re-enable after drop to allow normal constraints on create
            with db.engine.begin() as conn:
                conn.execute(text('SET FOREIGN_KEY_CHECKS=1'))

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
        
        # 3. Additional demo scenarios: vouchers, orders, returns/refunds, loyalty, tickets, OTP, trusted devices
        print("--- Seeding demo scenarios (orders, returns, refunds, vouchers...) ---")
        try:
            from eacis.models.voucher import Voucher
            from eacis.models.order import Order, OrderItem
            from eacis.models.return_request import ReturnRequest
            from eacis.models.refund_transaction import RefundTransaction
            from eacis.models.loyalty import LoyaltyTransaction
            from eacis.models.inquiry_ticket import InquiryTicket
            from eacis.models.otp_challenge import OtpChallenge
            from eacis.models.trusted_device import TrustedDevice
            from eacis.models.audit import AuditLog
            from eacis.models.installment import InstallmentPlan, InstallmentSchedule
        except Exception:
            # fallback to non-package imports when run differently
            from models.voucher import Voucher
            from models.order import Order, OrderItem
            from models.return_request import ReturnRequest
            from models.refund_transaction import RefundTransaction
            from models.loyalty import LoyaltyTransaction
            from models.inquiry_ticket import InquiryTicket
            from models.otp_challenge import OtpChallenge
            from models.trusted_device import TrustedDevice
            from models.audit import AuditLog
            from models.installment import InstallmentPlan, InstallmentSchedule

        # Ensure any newly imported model tables exist (create missing tables)
        db.create_all()

        now = datetime.utcnow()

        # Voucher
        v_demo = Voucher(
            voucher_ref='VCH-DEMO10',
            code='DEMO10',
            discount_type='percent',
            discount_value=Decimal('10.00'),
            valid_from=now,
            valid_until=now.replace(year=now.year + 1),
            is_active=True,
            per_user_limit=1,
        )
        db.session.add(v_demo)
        db.session.commit()

        # Create a few orders to represent common scenarios
        print('Creating demo orders...')
        # helper to fetch product
        def get_prod(ref):
            return Product.query.filter_by(product_ref=ref).first()

        # Order 1: Delivered, full payment
        p1 = get_prod('REF-001') or Product.query.first()
        order1 = Order(
            order_ref='ORD-1001',
            customer_id=customer.id,
            status='delivered',
            subtotal=p1.price,
            discount=0,
            shipping_fee=Decimal('250.00'),
            tax=Decimal('0.00'),
            total=(p1.price + Decimal('250.00')),
            payment_method='full_pay',
            payment_ref='PM-ORD-1001',
            shipping_address={'line1': customer.address_line1 or ''},
            created_at=now,
            paid_at=now,
            shipped_at=now,
            delivered_at=now,
        )
        db.session.add(order1)
        db.session.commit()
        oi1 = OrderItem(order_id=order1.id, product_id=p1.id, quantity=1, unit_price=p1.price, subtotal=p1.price)
        db.session.add(oi1)
        db.session.commit()

        # Award loyalty for order1
        lt1 = LoyaltyTransaction(user_id=customer.id, type='earn', points=50, reference=order1.order_ref, note='Earn points for ORD-1001')
        db.session.add(lt1)

        # Order 2: Shipped, paid
        p2 = get_prod('AC-001') or p1
        order2 = Order(
            order_ref='ORD-1002',
            customer_id=customer.id,
            status='shipped',
            subtotal=p2.price,
            discount=0,
            shipping_fee=Decimal('300.00'),
            tax=Decimal('0.00'),
            total=(p2.price + Decimal('300.00')),
            payment_method='full_pay',
            payment_ref='PM-ORD-1002',
            shipping_address={'line1': customer.address_line1 or ''},
            created_at=now,
            paid_at=now,
            shipped_at=now,
        )
        db.session.add(order2)
        db.session.commit()
        oi2 = OrderItem(order_id=order2.id, product_id=p2.id, quantity=1, unit_price=p2.price, subtotal=p2.price)
        db.session.add(oi2)

        # Order 3: Paid then return requested -> refunded
        p3 = get_prod('WM-001') or p1
        order3 = Order(
            order_ref='ORD-1003',
            customer_id=customer.id,
            status='refunded',
            subtotal=p3.price,
            discount=0,
            shipping_fee=Decimal('200.00'),
            tax=Decimal('0.00'),
            total=(p3.price + Decimal('200.00')),
            payment_method='full_pay',
            payment_ref='PM-ORD-1003',
            shipping_address={'line1': customer.address_line1 or ''},
            created_at=now,
            paid_at=now,
        )
        db.session.add(order3)
        db.session.commit()
        oi3 = OrderItem(order_id=order3.id, product_id=p3.id, quantity=1, unit_price=p3.price, subtotal=p3.price)
        db.session.add(oi3)
        db.session.commit()

        # Create ReturnRequest for order3 and a processed RefundTransaction
        rrt = ReturnRequest(
            rrt_ref='RRT-1001',
            order_id=order3.id,
            customer_id=customer.id,
            reason='Defective item',
            description='Unit arrived with visible damage on front panel.',
            status='refund_requested',
            refund_amount=p3.price,
        )
        db.session.add(rrt)
        db.session.commit()

        refund = RefundTransaction(
            refund_ref='RFND-1001',
            return_request_id=rrt.id,
            amount=rrt.refund_amount,
            status='processed',
        )
        db.session.add(refund)

        # Increment voucher usage example by applying to order2
        order2.voucher_id = v_demo.id
        v_demo.uses_count = (v_demo.uses_count or 0) + 1

        # Inquiry ticket (escalation example)
        ticket = InquiryTicket(
            ticket_ref='TCK-1001',
            customer_id=customer.id,
            order_id=order3.id,
            assigned_to=seller_v.id,
            subject='Damaged on arrival',
            description='Customer reports visible damage. Requesting refund/resolution.',
            priority='high',
            status='open'
        )
        db.session.add(ticket)

        # Trusted device and OTP samples
        try:
            td = TrustedDevice(user_id=customer.id, token_hash='demo-token-hash-cust', device_name='Demo Customer Device')
            db.session.add(td)
        except Exception:
            app.logger.exception('Could not create TrustedDevice demo row; skipping')

        try:
            otp = OtpChallenge(user_id=customer.id, email=customer.email, purpose='login', code_hash='demo-otp-hash', expires_at=now)
            db.session.add(otp)
        except Exception:
            app.logger.exception('Could not create OtpChallenge demo row; skipping')

        # Audit log entries
        al = AuditLog(actor_id=admin.id, actor_name=admin.full_name, role='admin', action='seed_demo_data', module='seed', target_ref='ORD-1001', meta={'note': 'Demo seed created'})
        db.session.add(al)

        db.session.commit()

        print('\n--- DEMO DATA READY ---')
        print(f'Customer: {customer.email} / customer123')
        print(f'Seller (Verified): {seller_v.email} / seller123')
        print(f'Seller (Pending): {seller_u.email} / seller123')
        print(f'Admin: {admin.email} / admin123')
        print('Sample orders: ORD-1001, ORD-1002, ORD-1003')
        print('Return request: RRT-1001 -> Refund RFND-1001')
        print('Voucher: DEMO10 (VCH-DEMO10)')
        print('------------------------')

if __name__ == "__main__":
    seed_database()
