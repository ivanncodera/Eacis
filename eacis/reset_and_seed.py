import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text

# Ensure we're in the right path to import eacis
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.user import User
from eacis.models.product import Product
import shutil
import re

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
            phone='09171234567',
            business_permit_path='permits/demo_permit.pdf',
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
        
        # Products derived from user-provided catalog (remove anything not listed)
        products_to_seed = [
            # Kitchen & Cooking
            {'name': 'Two-Door Refrigerator (10 cu. ft.)', 'ref': 'REF-001', 'price': Decimal('18000.00'), 'stock': 12, 'category': 'Kitchen & Cooking', 'image': '2-door-refrigirator.webp', 'desc': 'Inverter, frost-free 2-door refrigerator.'},
            {'name': 'Single Door Refrigerator (6 cu. ft.)', 'ref': 'REF-002', 'price': Decimal('8500.00'), 'stock': 20, 'category': 'Kitchen & Cooking', 'image': 'single-door-ref.webp', 'desc': 'Compact single-door refrigerator.'},
            {'name': 'Inverter Chest Freezer', 'ref': 'FRZ-001', 'price': Decimal('11000.00'), 'stock': 8, 'category': 'Kitchen & Cooking', 'image': 'inverted-chest-freezer.webp', 'desc': 'Chest freezer with inverter technology.'},
            {'name': 'Gas Range with Oven (4 Burners)', 'ref': 'GR-001', 'price': Decimal('14500.00'), 'stock': 6, 'category': 'Kitchen & Cooking', 'image': 'gas-range-with-oven-4-burners.webp', 'desc': '4-burner gas range with integrated oven.'},
            {'name': 'Induction Cooker (Double Zone)', 'ref': 'IND-DBL-001', 'price': Decimal('4500.00'), 'stock': 30, 'category': 'Kitchen & Cooking', 'image': 'induction-cooker-double.png', 'desc': 'Double zone induction cooker, touch control.'},
            {'name': 'Single Burner Induction Cooker', 'ref': 'IND-001', 'price': Decimal('1800.00'), 'stock': 50, 'category': 'Kitchen & Cooking', 'image': 'single-burner-induction-cooker.webp', 'desc': 'Portable single burner induction cooker.'},
            {'name': 'Microwave Oven (20L)', 'ref': 'MW-001', 'price': Decimal('3200.00'), 'stock': 25, 'category': 'Kitchen & Cooking', 'image': 'microwave-oven.jfif', 'desc': '20L microwave oven with defrost function.'},
            {'name': 'Air Fryer (5L)', 'ref': 'AF-001', 'price': Decimal('2800.00'), 'stock': 40, 'category': 'Kitchen & Cooking', 'image': 'air-fryer.jfif', 'desc': 'Digital air fryer with touch controls.'},
            {'name': 'Electric Oven/Rotisserie (35L)', 'ref': 'EO-001', 'price': Decimal('4000.00'), 'stock': 10, 'category': 'Kitchen & Cooking', 'image': 'electric-oven-rotisserie.webp', 'desc': 'Electric oven/rotisserie fits whole chicken.'},
            {'name': 'Rice Cooker (1.8L)', 'ref': 'RC-001', 'price': Decimal('1500.00'), 'stock': 60, 'category': 'Kitchen & Cooking', 'image': 'rice-cooker.jpg', 'desc': '1.8L rice cooker with steamer.'},
            {'name': 'Electric Kettle (1.7L)', 'ref': 'EK-001', 'price': Decimal('800.00'), 'stock': 80, 'category': 'Kitchen & Cooking', 'image': 'electric-kettle.webp', 'desc': 'Cordless stainless steel electric kettle.'},
            {'name': 'Stand Mixer', 'ref': 'SM-001', 'price': Decimal('4500.00'), 'stock': 15, 'category': 'Kitchen & Cooking', 'image': 'stand-mixer.jfif', 'desc': 'Stand mixer with stainless steel bowl.'},
            {'name': 'Electric Food Processor', 'ref': 'FP-001', 'price': Decimal('2200.00'), 'stock': 20, 'category': 'Kitchen & Cooking', 'image': 'electric-food-processor.jfif', 'desc': 'Multi-functional food processor with blades.'},
            {'name': 'Blender (1.5L)', 'ref': 'BL-001', 'price': Decimal('1600.00'), 'stock': 25, 'category': 'Kitchen & Cooking', 'image': 'blender.jfif', 'desc': 'Glass jar blender with pulse function.'},
            {'name': 'Coffee Maker (Drip type)', 'ref': 'CM-001', 'price': Decimal('1200.00'), 'stock': 30, 'category': 'Kitchen & Cooking', 'image': 'coffee-maker.jfif', 'desc': 'Drip coffee maker, 10-12 cup capacity.'},
            {'name': 'Espresso Machine (Home Entry-level)', 'ref': 'EM-001', 'price': Decimal('6500.00'), 'stock': 8, 'category': 'Kitchen & Cooking', 'image': 'espresso-machine.jfif', 'desc': 'Entry-level espresso machine, 15-bar.'},
            {'name': 'Bread Toaster (2-Slice)', 'ref': 'BT-001', 'price': Decimal('900.00'), 'stock': 40, 'category': 'Kitchen & Cooking', 'image': 'bread-toaster.jfif', 'desc': '2-slice pop-up toaster with browning control.'},
            {'name': 'Sandwich Maker/Waffle Iron', 'ref': 'SMW-001', 'price': Decimal('1100.00'), 'stock': 35, 'category': 'Kitchen & Cooking', 'image': 'sandwich-maker.jfif', 'desc': 'Non-stick sandwich maker / waffle iron.'},
            {'name': 'Juice Extractor', 'ref': 'JE-001', 'price': Decimal('2500.00'), 'stock': 20, 'category': 'Kitchen & Cooking', 'image': 'juice-extractor.jfif', 'desc': 'Wide-mouth centrifugal juice extractor.'},
            {'name': 'Slow Cooker (3.5L)', 'ref': 'SC-001', 'price': Decimal('1800.00'), 'stock': 22, 'category': 'Kitchen & Cooking', 'image': 'slow-cooker.jfif', 'desc': '3.5L ceramic slow cooker.'},
            {'name': 'Dishwasher (Countertop)', 'ref': 'DW-001', 'price': Decimal('12000.00'), 'stock': 6, 'category': 'Kitchen & Cooking', 'image': 'dishwasher-countertop.jfif', 'desc': 'Compact countertop dishwasher, 6 settings.'},
            {'name': 'Water Dispenser (Top Load)', 'ref': 'WD-001', 'price': Decimal('3500.00'), 'stock': 18, 'category': 'Kitchen & Cooking', 'image': 'water-dispenser.webp', 'desc': 'Top-load water dispenser with hot & cold taps.'},

            # Laundry & Cleaning
            {'name': 'Fully Automatic Washing Machine (7kg)', 'ref': 'FA-001', 'price': Decimal('13500.00'), 'stock': 10, 'category': 'Laundry & Cleaning', 'image': 'fully-automatic-washing-machine.jfif', 'desc': '7kg fully automatic washing machine.'},
            {'name': 'Front Load Washing Machine (8kg)', 'ref': 'WM-001', 'price': Decimal('22000.00'), 'stock': 5, 'category': 'Laundry & Cleaning', 'image': 'frontload-washing-machine.jpg', 'desc': '8kg front load energy efficient washing machine.'},
            {'name': 'Twin Tub Washing Machine', 'ref': 'TT-001', 'price': Decimal('5500.00'), 'stock': 20, 'category': 'Laundry & Cleaning', 'image': 'twin-tub-wm.webp', 'desc': 'Manual twin tub washer and spinner.'},
            {'name': 'Electric Clothes Dryer', 'ref': 'DR-001', 'price': Decimal('15000.00'), 'stock': 5, 'category': 'Laundry & Cleaning', 'image': 'electric-clothes-dryer.webp', 'desc': '7kg tumble dryer.'},
            {'name': 'Spin Dryer (Small)', 'ref': 'SD-001', 'price': Decimal('2500.00'), 'stock': 30, 'category': 'Laundry & Cleaning', 'image': 'spin-dryer.jfif', 'desc': 'Portable spin dryer 5kg.'},
            {'name': 'Vacuum Cleaner (Bagless Canister)', 'ref': 'VC-001', 'price': Decimal('4200.00'), 'stock': 15, 'category': 'Laundry & Cleaning', 'image': 'vacuum-cleaner.jfif', 'desc': 'Bagless canister vacuum with HEPA filter.'},
            {'name': 'Robot Vacuum', 'ref': 'RV-001', 'price': Decimal('7500.00'), 'stock': 10, 'category': 'Laundry & Cleaning', 'image': 'robot-vacuum.jfif', 'desc': 'App-controlled self-charging robot vacuum.'},
            {'name': 'Wet & Dry Vacuum (Industrial style)', 'ref': 'WDV-001', 'price': Decimal('3800.00'), 'stock': 8, 'category': 'Laundry & Cleaning', 'image': 'wet-and-dry-vacuum-cleaner.jfif', 'desc': 'Heavy-duty wet and dry vacuum cleaner.'},
            {'name': 'Steam Iron', 'ref': 'SI-001', 'price': Decimal('1200.00'), 'stock': 40, 'category': 'Laundry & Cleaning', 'image': 'steam-iron.webp', 'desc': 'Non-stick soleplate steam iron.'},
            {'name': 'Garment Steamer (Standing)', 'ref': 'GS-001', 'price': Decimal('2800.00'), 'stock': 15, 'category': 'Laundry & Cleaning', 'image': 'garment-steamer.webp', 'desc': 'Standing garment steamer with telescopic pole.'},

            # Cooling & Air Quality
            {'name': 'Split Type Aircon (1.5 HP)', 'ref': 'AC-001', 'price': Decimal('25000.00'), 'stock': 5, 'category': 'Cooling & Air Quality', 'image': 'split-type-aircon.webp', 'desc': '1.5 HP inverter split type air conditioner.'},
            {'name': 'Window Type Aircon (0.5 HP)', 'ref': 'WAC-001', 'price': Decimal('7500.00'), 'stock': 8, 'category': 'Cooling & Air Quality', 'image': 'window-ac.webp', 'desc': '0.5 HP window type aircon.'},
            {'name': 'Portable Air Conditioner', 'ref': 'PAC-001', 'price': Decimal('10000.00'), 'stock': 6, 'category': 'Cooling & Air Quality', 'image': 'portable-ac.webp', 'desc': '1 HP portable air conditioner.'},
            {'name': 'Electric Stand Fan (16 inch)', 'ref': 'FS-001', 'price': Decimal('1400.00'), 'stock': 30, 'category': 'Cooling & Air Quality', 'image': 'stand-fan.webp', 'desc': '16-inch stand fan, 3-speed.'},
            {'name': 'Electric Wall Fan', 'ref': 'WF-001', 'price': Decimal('1200.00'), 'stock': 25, 'category': 'Cooling & Air Quality', 'image': 'wall-fan.webp', 'desc': 'Wall-mounted electric fan, remote control.'},
            {'name': 'Box Fan', 'ref': 'BF-001', 'price': Decimal('900.00'), 'stock': 40, 'category': 'Cooling & Air Quality', 'image': 'box-fan.jfif', 'desc': 'Compact box fan with rotating grill.'},
            {'name': 'Air Purifier', 'ref': 'AP-001', 'price': Decimal('4500.00'), 'stock': 12, 'category': 'Cooling & Air Quality', 'image': 'air-purifier.webp', 'desc': 'HEPA air purifier with CADR rating.'},
            {'name': 'Dehumidifier', 'ref': 'DH-001', 'price': Decimal('6000.00'), 'stock': 10, 'category': 'Cooling & Air Quality', 'image': 'dehumidifier.jfif', 'desc': 'Dehumidifier for moisture control.'},

            # Home Entertainment & Gadgets
            {'name': 'Smart TV (55-inch 4K)', 'ref': 'TV-55-001', 'price': Decimal('22000.00'), 'stock': 10, 'category': 'Home Entertainment & Gadgets', 'image': 'smart-tv.jfif', 'desc': '55-inch 4K smart TV with apps.'},
            {'name': 'Smart TV (32-inch)', 'ref': 'TV-32-001', 'price': Decimal('7000.00'), 'stock': 20, 'category': 'Home Entertainment & Gadgets', 'image': 'smart-tv-32.jfif', 'desc': '32-inch HD-ready smart TV.'},
            {'name': 'Soundbar with Subwoofer', 'ref': 'SB-001', 'price': Decimal('6500.00'), 'stock': 15, 'category': 'Home Entertainment & Gadgets', 'image': 'soundbar.jfif', 'desc': 'Soundbar with wireless subwoofer.'},
            {'name': 'Home Theater System (5.1)', 'ref': 'HTS-001', 'price': Decimal('12500.00'), 'stock': 5, 'category': 'Home Entertainment & Gadgets', 'image': 'home-theater-system.jfif', 'desc': '5.1 surround sound home theater system.'},
            {'name': 'Videoke Machine/Portable Speaker', 'ref': 'VM-001', 'price': Decimal('5000.00'), 'stock': 12, 'category': 'Home Entertainment & Gadgets', 'image': 'videoke-machine.jfif', 'desc': 'Portable videoke machine with wireless mic.'},
            {'name': 'Desktop Computer (Mid-range)', 'ref': 'PC-001', 'price': Decimal('18000.00'), 'stock': 8, 'category': 'Home Entertainment & Gadgets', 'image': 'desktop-computer.webp', 'desc': 'Mid-range desktop computer bundle.'},
            {'name': 'Uninterruptible Power Supply (UPS)', 'ref': 'UPS-001', 'price': Decimal('2200.00'), 'stock': 30, 'category': 'Home Entertainment & Gadgets', 'image': 'uninterruptable-power-supply.jfif', 'desc': 'UPS for PC backup.'},
            {'name': 'Rechargeable Emergency Light', 'ref': 'REL-001', 'price': Decimal('800.00'), 'stock': 50, 'category': 'Home Entertainment & Gadgets', 'image': 'rechargeable-emergency-light.jfif', 'desc': 'LED rechargeable emergency light.'},
            {'name': 'Digital Door Lock', 'ref': 'DDL-001', 'price': Decimal('4000.00'), 'stock': 10, 'category': 'Home Entertainment & Gadgets', 'image': 'digital-door-lock.webp', 'desc': 'Fingerprint/PIN digital door lock.'},
            {'name': 'UV Sterilizer Cabinet', 'ref': 'UVS-001', 'price': Decimal('3500.00'), 'stock': 6, 'category': 'Home Entertainment & Gadgets', 'image': 'uv-sterilizer-cabinet.webp', 'desc': 'UV sterilizer cabinet for baby bottles and gadgets.'},
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
        # Assign images from the assets folder into instance uploads for each product
        try:
            assets_dir = os.path.join(app.root_path, 'static', 'assets', 'products')
            uploads_root = os.path.join(app.instance_path, 'uploads', 'products')
            if os.path.isdir(assets_dir):
                available = [f for f in sorted(os.listdir(assets_dir)) if os.path.isfile(os.path.join(assets_dir, f)) and f.lower().endswith(('.jpg','.jpeg','.png','.webp','.jfif'))]
                if available:
                    prods = Product.query.filter_by(seller_id=seller_v.id).order_by(Product.id).all()

                    def pick_asset_for_product_name(name, category):
                        # Normalized name for comparisons
                        n = re.sub(r"[^a-z0-9 ]", ' ', (name or '').lower())
                        lname = n.strip()

                        # Manual explicit mappings for high-confidence matches
                        manual_map = {
                            'air fryer': 'air-fryer.jfif',
                            'airfryer': 'air-fryer.jfif',
                            'blender': 'blender.jfif',
                            'box fan': 'box-fan.jfif',
                            'bread toaster': 'bread-toaster.jfif',
                            'toaster': 'bread-toaster.jfif',
                            'coffee maker': 'coffee-maker.jfif',
                            'espresso': 'espresso-machine.jfif',
                            'dehumidifier': 'dehumidifier.jfif',
                            'dishwasher': 'dishwasher-countertop.jfif',
                            'food processor': 'electric-food-processor.jfif',
                            'juice extractor': 'juice-extractor.jfif',
                            'microwave': 'microwave-oven.jfif',
                            'rechargeable emergency': 'rechargeable-emergency-light.jfif',
                            'robot vacuum': 'robot-vacuum.jfif',
                            'sandwich': 'sandwich-maker.jfif',
                            'slow cooker': 'slow-cooker.jfif',
                            'smart tv 32': 'smart-tv-32.jfif',
                            'smart tv': 'smart-tv.jfif',
                            'soundbar': 'soundbar.jfif',
                            'spin dryer': 'spin-dryer.jfif',
                            'stand mixer': 'stand-mixer.jfif',
                            'ups': 'uninterruptable-power-supply.jfif',
                            'vacuum cleaner': 'vacuum-cleaner.jfif',
                            'videoke': 'videoke-machine.jfif',
                            'wet and dry': 'wet-and-dry-vacuum-cleaner.jfif',
                            'fully automatic washing': 'fully-automatic-washing-machine.jfif',
                            'washing machine': 'fully-automatic-washing-machine.jfif',
                            'spin': 'spin-dryer.jfif',
                        }

                        # Apply manual map when an asset exists for the mapping
                        for key, asset_name in manual_map.items():
                            if key in lname or (category and key in (category or '').lower()):
                                if asset_name in available:
                                    return asset_name

                        # Prefer assets that share keywords with the product name
                        words = set(lname.split())
                        # avoid matching on short/generic tokens like "door" or numeric tokens
                        stopwords = {'the', 'and', 'with', 'for', 'two', '2', '1', 'inch', 'cu', 'ft', 'l', 'kg', 'door', 'type'}
                        for asset in available:
                            base = os.path.splitext(asset)[0].lower()
                            parts = set(re.sub(r"[^a-z0-9 ]", ' ', base).split())
                            intersection = parts & words
                            # filter out stopwords and short tokens
                            intersection = {w for w in intersection if w not in stopwords and len(w) > 2}
                            if intersection:
                                return asset

                        # Fallback by category keywords
                        cat = (category or '').lower()
                        category_preferences = {
                            'kitchen': ['microwave', 'air', 'fryer', 'blender', 'coffee', 'toaster', 'dishwasher', 'oven', 'juice', 'slow', 'rice', 'kettle', 'mixer', 'sandwich', 'processor'],
                            'laundry': ['washing', 'washer', 'dryer', 'spin'],
                            'cooling': ['air', 'fan', 'dehumidifier', 'ac', 'box'],
                            'cleaning': ['vacuum', 'robot', 'wet', 'dry'],
                            'entertainment': ['tv', 'smart', 'soundbar', 'home', 'videoke'],
                        }
                        for key, prefs in category_preferences.items():
                            if key in cat:
                                for pref in prefs:
                                    for asset in available:
                                        if pref in asset.lower():
                                            return asset

                        # Final fallback: return the first available asset
                        return available[0]

                    # Deterministic mappings for high-confidence product->asset matches
                    fixed_ref_asset_map = {
                        'AF-001': 'air-fryer.jfif',
                        'BL-001': 'blender.jfif',
                        'BF-001': 'box-fan.jfif',
                        'BT-001': 'bread-toaster.jfif',
                        'CM-001': 'coffee-maker.jfif',
                        'DH-001': 'dehumidifier.jfif',
                        'DW-001': 'dishwasher-countertop.jfif',
                        'FP-001': 'electric-food-processor.jfif',
                        'EM-001': 'espresso-machine.jfif',
                        'FA-001': 'fully-automatic-washing-machine.jfif',
                        'HTS-001': 'home-theater-system.jfif',
                        'JE-001': 'juice-extractor.jfif',
                        'MW-001': 'microwave-oven.jfif',
                        'REL-001': 'rechargeable-emergency-light.jfif',
                        'RV-001': 'robot-vacuum.jfif',
                        'SMW-001': 'sandwich-maker.jfif',
                        'SC-001': 'slow-cooker.jfif',
                        'TV-32-001': 'smart-tv-32.jfif',
                        'TV-55-001': 'smart-tv.jfif',
                        'SB-001': 'soundbar.jfif',
                        'SD-001': 'spin-dryer.jfif',
                        'SM-001': 'stand-mixer.jfif',
                        'UPS-001': 'uninterruptable-power-supply.jfif',
                        'VC-001': 'vacuum-cleaner.jfif',
                        'VM-001': 'videoke-machine.jfif',
                        'WDV-001': 'wet-and-dry-vacuum-cleaner.jfif',
                    }

                    # Assign the most appropriate asset to each seeded product and copy it to uploads
                    for prod in prods:
                        # prefer explicit per-ref mapping when available
                        chosen = None
                        mapped = fixed_ref_asset_map.get(prod.product_ref)
                        if mapped and mapped in available:
                            chosen = mapped
                        else:
                            chosen = pick_asset_for_product_name(prod.name, prod.category)
                        src = os.path.join(assets_dir, chosen)
                        dest_dir = os.path.join(uploads_root, prod.product_ref)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest = os.path.join(dest_dir, chosen)
                        try:
                            shutil.copy(src, dest)
                            prod.image_url = f"/uploads/products/{prod.product_ref}/{chosen}"
                            db.session.add(prod)
                        except Exception:
                            app.logger.exception(f'Could not copy asset {src} -> {dest}; leaving original image_url')
                    db.session.commit()
                    # Do not create extra products automatically from any remaining asset images.
                    # We intentionally avoid creating products that are not listed in the provided catalog.
        except Exception:
            app.logger.exception('Error while copying product assets into uploads; continuing')
        # 2.5 Seed product reviews and stars (customers who reviewed / starred products)
        print('--- Seeding Reviews & Stars ---')
        try:
            from eacis.models.review import Review
            from eacis.models.product_star import ProductStar
        except Exception:
            from models.review import Review
            from models.product_star import ProductStar

        # Add extra reviewer users
        reviewer1 = User(
            email='reviewer1@demo.com',
            role='customer',
            full_name='Reviewer One',
            first_name='Reviewer',
            last_name='One',
            is_active=True
        )
        reviewer1.set_password('reviewer123')
        db.session.add(reviewer1)

        reviewer2 = User(
            email='reviewer2@demo.com',
            role='customer',
            full_name='Reviewer Two',
            first_name='Reviewer',
            last_name='Two',
            is_active=True
        )
        reviewer2.set_password('reviewer123')
        db.session.add(reviewer2)
        db.session.commit()

        # helper to fetch product
        def _get(ref):
            return Product.query.filter_by(product_ref=ref).first()

        p_ref_1 = _get('REF-001')
        p_ref_2 = _get('AC-001')
        p_ref_3 = _get('WM-001')

        if p_ref_1:
            existing_r1 = Review.query.filter_by(product_id=p_ref_1.id, user_id=customer.id).first()
            if not existing_r1:
                r1 = Review(product_id=p_ref_1.id, user_id=customer.id, rating=5, title='Fantastic fridge', body='Keeps food fresh, very quiet.', reviewer_name=customer.full_name, is_approved=True)
                db.session.add(r1)
            # avoid duplicate stars if the same (product,user) pair exists
            existing_ps = ProductStar.query.filter_by(product_id=p_ref_1.id, user_id=customer.id).first()
            if not existing_ps:
                ps1 = ProductStar(product_id=p_ref_1.id, user_id=customer.id)
                db.session.add(ps1)

        if p_ref_2:
            existing_r2 = Review.query.filter_by(product_id=p_ref_2.id, user_id=reviewer1.id).first()
            if not existing_r2:
                r2 = Review(product_id=p_ref_2.id, user_id=reviewer1.id, rating=4, title='Great AC', body='Cools fast and efficient.', reviewer_name=reviewer1.full_name, is_approved=True)
                db.session.add(r2)
            # anonymous review example
            existing_r2a = Review.query.filter_by(product_id=p_ref_2.id, user_id=reviewer2.id).first()
            if not existing_r2a:
                r2a = Review(product_id=p_ref_2.id, user_id=reviewer2.id, rating=3, title='Good but noisy', body='A bit louder than expected.', is_anonymous=True, is_approved=True)
                db.session.add(r2a)

        if p_ref_3:
            # unapproved review example (moderation)
            existing_r3 = Review.query.filter_by(product_id=p_ref_3.id, user_id=reviewer2.id).first()
            if not existing_r3:
                r3 = Review(product_id=p_ref_3.id, user_id=reviewer2.id, rating=2, title='Faulty unit', body='Stopped working after 2 washes.', reviewer_name=reviewer2.full_name, is_approved=False)
                db.session.add(r3)

        db.session.commit()
        print('Reviews and product stars seeded.')
        
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
            # Avoid duplicate trusted-device token_hash collisions on repeated runs
            existing_td = TrustedDevice.query.filter_by(token_hash='demo-token-hash-cust').first()
            if not existing_td:
                td = TrustedDevice(user_id=customer.id, token_hash='demo-token-hash-cust', device_name='Demo Customer Device')
                db.session.add(td)
        except Exception:
            app.logger.exception('Could not create TrustedDevice demo row; skipping')

        try:
            # Create a dev-only fixed OTP for seeded demo accounts (non-production only).
            if str(app.config.get('FLASK_ENV') or '').lower() != 'production':
                try:
                    from eacis.services.otp_service import _hash_code
                except Exception:
                    try:
                        from ..services.otp_service import _hash_code
                    except Exception:
                        from services.otp_service import _hash_code
                try:
                    from eacis.models.otp_challenge import OtpChallenge
                except Exception:
                    try:
                        from models.otp_challenge import OtpChallenge
                    except Exception:
                        OtpChallenge = None

                default_code = str(app.config.get('DEV_SEED_FIXED_OTP') or '123456')
                code_len = int(app.config.get('OTP_CODE_LENGTH') or 6)
                if len(default_code) >= code_len:
                    fixed_code = default_code[:code_len]
                else:
                    fixed_code = default_code + ('1' * (code_len - len(default_code)))

                if OtpChallenge is not None:
                    existing = OtpChallenge.query.filter_by(email=customer.email, purpose='login').order_by(OtpChallenge.created_at.desc()).first()
                    expires = datetime.utcnow() + timedelta(days=3650)
                    if existing:
                        existing.code_hash = _hash_code(fixed_code)
                        existing.expires_at = expires
                        existing.meta = dict(existing.meta or {}, debug_code=fixed_code, dev_preview=True, seed_account=True)
                        db.session.add(existing)
                    else:
                        ch = OtpChallenge(user_id=customer.id, email=customer.email, purpose='login', code_hash=_hash_code(fixed_code), expires_at=expires, sent_to=customer.email, meta={'debug_code': fixed_code, 'dev_preview': True, 'seed_account': True})
                        db.session.add(ch)
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

        # Extended demo seeds: create extra demo/test products, vouchers, installment
        # orders with paid/unpaid/overdue schedules, and seed activity for sellers/admin.
        print('\n--- Seeding extended demo scenarios (extra products, installments, vouchers) ---')
        try:
            # small helper to safely create if missing
            def _get_or_create_product(ref, name, price, stock=5, category='Kitchen & Cooking', image='demo-placeholder.jfif', desc='Appliance product', is_active=True, created_offset_days=30):
                p = Product.query.filter_by(product_ref=ref).first()
                if p:
                    return p
                comp = (price * Decimal('1.15')).quantize(Decimal('100.00'))
                p = Product(product_ref=ref, seller_id=seller_v.id, name=name, category=category, description=desc, price=price, compare_price=comp, stock=stock, image_url=f"/static/assets/products/{image}", installment_enabled=True, is_active=is_active, weight_kg=Decimal('5.0'), created_at=now - timedelta(days=created_offset_days))
                db.session.add(p)
                db.session.commit()
                return p

            # create extra background fixtures (kept inactive so raw test fixtures do not clutter public storefront)
            extra_products = [
                ('DEMO-001', 'Compact Emergency Lantern', Decimal('1000.00'), 'Home Entertainment & Gadgets'),
                ('DEMO-002', 'Smart Plug & Energy Monitor', Decimal('5000.00'), 'Home Entertainment & Gadgets'),
                ('DEMO-003', 'Surge Protector Strip', Decimal('500.00'), 'Home Entertainment & Gadgets'),
                ('DEMO-004', 'Commercial Chest Freezer (15 cu. ft.)', Decimal('13000.00'), 'Kitchen & Cooking'),
                ('DEMO-005', 'Cordless Stick Vacuum', Decimal('8000.00'), 'Laundry & Cleaning'),
            ]
            created_demo = []
            for ref, name, price, cat in extra_products:
                created_demo.append(_get_or_create_product(ref, name, price, stock=8, category=cat, image='rechargeable-emergency-light.jfif', desc=f'{name} with official warranty.', is_active=False, created_offset_days=60))

            # Reuse existing assets when possible: copy first available asset into demo product uploads
            try:
                assets_dir = os.path.join(app.root_path, 'static', 'assets', 'products')
                uploads_root = os.path.join(app.instance_path, 'uploads', 'products')
                available = [f for f in sorted(os.listdir(assets_dir)) if os.path.isfile(os.path.join(assets_dir, f))] if os.path.isdir(assets_dir) else []
            except Exception:
                available = []

            for i, p in enumerate(created_demo):
                if available:
                    chosen = available[i % len(available)]
                    src = os.path.join(assets_dir, chosen)
                    dest_dir = os.path.join(uploads_root, p.product_ref)
                    os.makedirs(dest_dir, exist_ok=True)
                    try:
                        shutil.copy(src, os.path.join(dest_dir, chosen))
                        p.image_url = f"/uploads/products/{p.product_ref}/{chosen}"
                        db.session.add(p)
                        db.session.commit()
                    except Exception:
                        app.logger.exception('Could not copy demo asset; skipping')

            # Create extra vouchers (one unclaimed, one seller-targeted)
            v_unclaimed = Voucher.query.filter_by(code='UNCLAIMED2026').first()
            if not v_unclaimed:
                v_unclaimed = Voucher(voucher_ref='VCH-UNCLAIM', code='UNCLAIMED2026', discount_type='fixed', discount_value=Decimal('250.00'), valid_from=now - timedelta(days=30), valid_until=now.replace(year=now.year + 1), is_active=True, uses_count=0)
                db.session.add(v_unclaimed)

            v_unclaim5 = Voucher.query.filter_by(code='UNCLAIM5').first()
            if not v_unclaim5:
                v_unclaim5 = Voucher(voucher_ref='VCH-UNCLAIM5', code='UNCLAIM5', discount_type='percent', discount_value=Decimal('5.00'), valid_from=now - timedelta(days=30), valid_until=now.replace(year=now.year + 1), is_active=True, uses_count=0)
                db.session.add(v_unclaim5)

            v_seller = Voucher.query.filter_by(code='SELL5').first()
            if not v_seller:
                v_seller = Voucher(voucher_ref='VCH-SELLER5', code='SELL5', discount_type='fixed', discount_value=Decimal('500.00'), valid_from=now - timedelta(days=10), valid_until=now.replace(year=now.year + 1), is_active=True, seller_id=seller_v.id, uses_count=0)
                db.session.add(v_seller)

            # Unpaid (pending) and past_due orders (ORD-1004, ORD-1005)
            if not Order.query.filter_by(order_ref='ORD-1004').first():
                o1004 = Order(order_ref='ORD-1004', customer_id=customer.id, status='pending', subtotal=p1.price, discount=0, shipping_fee=Decimal('250.00'), tax=Decimal('0.00'), total=p1.price + Decimal('250.00'), payment_method='full_pay', payment_ref='PM-ORD-1004', shipping_address={'line1': customer.address_line1 or ''}, created_at=now)
                db.session.add(o1004)
            if not Order.query.filter_by(order_ref='ORD-1005').first():
                o1005 = Order(order_ref='ORD-1005', customer_id=customer.id, status='past_due', subtotal=p1.price, discount=0, shipping_fee=Decimal('250.00'), tax=Decimal('0.00'), total=p1.price + Decimal('250.00'), payment_method='installment', payment_ref='PM-ORD-1005', shipping_address={'line1': customer.address_line1 or ''}, created_at=now - timedelta(days=45))
                db.session.add(o1005)

            # Reviewer 3 with flagged (unapproved) review
            reviewer3 = User.query.filter_by(email='reviewer3@demo.com').first()
            if not reviewer3:
                reviewer3 = User(email='reviewer3@demo.com', role='customer', full_name='Reviewer Three', first_name='Reviewer', last_name='Three', is_active=True, email_verified_at=now)
                reviewer3.set_password('reviewer123')
                db.session.add(reviewer3)
                db.session.flush()
            target_prod_for_flag = p_ref_3 or p1
            if target_prod_for_flag and not Review.query.filter_by(user_id=reviewer3.id, is_approved=False).first():
                db.session.add(Review(product_id=target_prod_for_flag.id, user_id=reviewer3.id, rating=1, title='Flagged review', body='Needs moderation check.', reviewer_name=reviewer3.full_name, is_approved=False))

            # Disputed/rejected return RRT-2002 with failed RefundTransaction
            rrt2 = ReturnRequest.query.filter_by(rrt_ref='RRT-2002').first()
            if not rrt2:
                rrt2 = ReturnRequest(rrt_ref='RRT-2002', order_id=order2.id, customer_id=customer.id, reason='Changed mind', description='Disputed return request.', status='rejected', refund_amount=p2.price)
                db.session.add(rrt2)
                db.session.flush()
                db.session.add(RefundTransaction(refund_ref='RFND-2002', return_request_id=rrt2.id, amount=p2.price, status='failed'))

            # Multi-seller demo accounts, products (S2-001, S3-001), and orders (ORD-3001, ORD-3002)
            s2 = User.query.filter_by(email='seller2@market.com').first()
            if not s2:
                s2 = User(email='seller2@market.com', role='seller', business_name='Metro Home Hub', first_name='Marco', last_name='Seller', seller_verification_status='approved', seller_code='SELLER03', is_active=True, email_verified_at=now)
                s2.set_password('seller123')
                db.session.add(s2)
                db.session.flush()
            s3 = User.query.filter_by(email='seller3@market.com').first()
            if not s3:
                s3 = User(email='seller3@market.com', role='seller', business_name='Prime Kitchen Co', first_name='Elena', last_name='Seller', seller_verification_status='approved', seller_code='SELLER04', is_active=True, email_verified_at=now)
                s3.set_password('seller123')
                db.session.add(s3)
                db.session.flush()

            p_s2 = Product.query.filter_by(product_ref='S2-001').first()
            if not p_s2:
                p_s2 = Product(product_ref='S2-001', seller_id=s2.id, name='Metro Smart Cooler', category='Cooling & Air Quality', description='High-efficiency inverter air cooler.', price=Decimal('9500.00'), compare_price=Decimal('11000.00'), stock=10, image_url='/static/assets/products/dehumidifier.jfif', installment_enabled=True, is_active=True, created_at=now - timedelta(hours=2))
                db.session.add(p_s2)
                db.session.flush()
            p_s3 = Product.query.filter_by(product_ref='S3-001').first()
            if not p_s3:
                p_s3 = Product(product_ref='S3-001', seller_id=s3.id, name='Prime Espresso Pro', category='Kitchen & Cooking', description='Barista-grade home espresso.', price=Decimal('11500.00'), compare_price=Decimal('13500.00'), stock=7, image_url='/static/assets/products/espresso-machine.jfif', installment_enabled=True, is_active=True, created_at=now - timedelta(hours=1))
                db.session.add(p_s3)
                db.session.flush()

            if not Order.query.filter_by(order_ref='ORD-3001').first():
                o3001 = Order(order_ref='ORD-3001', customer_id=customer.id, status='paid', subtotal=p_s2.price, discount=0, shipping_fee=Decimal('200.00'), tax=Decimal('0.00'), total=p_s2.price + Decimal('200.00'), payment_method='full_pay', payment_ref='PM-ORD-3001', shipping_address={'line1': customer.address_line1 or ''}, created_at=now, paid_at=now)
                db.session.add(o3001)
                db.session.flush()
                db.session.add(OrderItem(order_id=o3001.id, product_id=p_s2.id, quantity=1, unit_price=p_s2.price, subtotal=p_s2.price))
            if not Order.query.filter_by(order_ref='ORD-3002').first():
                o3002 = Order(order_ref='ORD-3002', customer_id=customer.id, status='delivered', subtotal=p_s3.price, discount=0, shipping_fee=Decimal('200.00'), tax=Decimal('0.00'), total=p_s3.price + Decimal('200.00'), payment_method='full_pay', payment_ref='PM-ORD-3002', shipping_address={'line1': customer.address_line1 or ''}, created_at=now, paid_at=now, delivered_at=now)
                db.session.add(o3002)
                db.session.flush()
                db.session.add(OrderItem(order_id=o3002.id, product_id=p_s3.id, quantity=1, unit_price=p_s3.price, subtotal=p_s3.price))

            db.session.commit()

            # Create installment orders with a variety of statuses
            def _create_installment_order(order_ref, product, cust, months=6, downpayment=Decimal('0.00'), status='pending', days_offset=0, paid_months=0):
                # Normalize order.status to the allowed enum values (guard against legacy values like 'completed')
                allowed_order_statuses = {'pending', 'paid', 'packed', 'shipped', 'delivered', 'past_due', 'refunded', 'cancelled'}
                status_in = (status or 'pending')
                s_low = str(status_in).lower()
                if s_low in allowed_order_statuses:
                    order_status = s_low
                elif s_low == 'completed':
                    order_status = 'paid'
                elif s_low == 'active':
                    # 'active' was used to denote plan active; map to a neutral order state
                    order_status = 'pending'
                else:
                    order_status = 'pending'

                ord_total = product.price + Decimal('250.00')
                o = Order(order_ref=order_ref, customer_id=cust.id, status=order_status, subtotal=product.price, discount=0, shipping_fee=Decimal('250.00'), tax=Decimal('0.00'), total=ord_total, payment_method='installment', payment_ref=f'PM-{order_ref}', shipping_address={'line1': cust.address_line1 or ''}, created_at=(now - timedelta(days=days_offset)), paid_at=(now - timedelta(days=days_offset) if paid_months>0 else None))
                db.session.add(o)
                db.session.commit()
                oi = OrderItem(order_id=o.id, product_id=product.id, quantity=1, unit_price=product.price, subtotal=product.price)
                db.session.add(oi)
                db.session.commit()

                # create plan
                monthly = ((ord_total - downpayment) / Decimal(months)).quantize(Decimal('0.01'))
                plan = InstallmentPlan(order_id=o.id, months=months, monthly_amount=monthly, downpayment=downpayment, total_interest=Decimal('0.00'), status='active')
                db.session.add(plan)
                db.session.commit()

                # create schedule entries
                for m in range(months):
                    due = (now + timedelta(days=30*(m+1)) - timedelta(days=days_offset)).date()
                    status_sched = 'pending'
                    paid_at = None
                    if m < paid_months:
                        status_sched = 'paid'
                        paid_at = now - timedelta(days=days_offset - m)
                    # mark past due for schedules earlier than now if plan has been set to defaulted
                    if status == 'past_due' and due < now.date():
                        status_sched = 'past_due'
                    s = InstallmentSchedule(plan_id=plan.id, due_date=due, amount=monthly, status=status_sched, paid_at=paid_at)
                    db.session.add(s)
                # finalize plan status based on parameters
                if status == 'completed':
                    plan.status = 'completed'
                elif status == 'past_due':
                    plan.status = 'defaulted'
                else:
                    plan.status = 'active'
                db.session.add(plan)
                db.session.commit()
                return o, plan

            # sample installment orders
            demo_p1 = _get_or_create_product('DEMO-010', 'Planetary Stand Mixer Pro (5L)', Decimal('8000.00'), stock=5, category='Kitchen & Cooking', image='stand-mixer.jfif', desc='Heavy-duty planetary stand mixer', is_active=False, created_offset_days=45)
            demo_p2 = _get_or_create_product('DEMO-011', 'Inverter Top-Load Washer (9kg)', Decimal('13000.00'), stock=3, category='Laundry & Cleaning', image='fully-automatic-washing-machine.jfif', desc='Smart inverter top-load washing machine', is_active=False, created_offset_days=45)
            # Completed (all paid)
            _create_installment_order('ORD-2001', demo_p1, customer, months=6, downpayment=Decimal('999.00'), status='completed', days_offset=60, paid_months=6)
            # Active (partial paid)
            _create_installment_order('ORD-2002', demo_p2, customer, months=12, downpayment=Decimal('1999.00'), status='active', days_offset=10, paid_months=2)
            # Overdue/defaulted (past due schedules)
            _create_installment_order('ORD-2003', demo_p2, customer, months=6, downpayment=Decimal('0.00'), status='past_due', days_offset=90, paid_months=1)

            # Use v_seller on a sample order to demonstrate seller-targeted vouchers
            sample_prod = Product.query.filter_by(product_ref='REF-001').first()
            if sample_prod:
                o_s = Order(order_ref='ORD-2010', customer_id=customer.id, status='paid', subtotal=sample_prod.price, discount=v_seller.discount_value if v_seller else 0, shipping_fee=Decimal('250.00'), tax=Decimal('0.00'), total=sample_prod.price - (v_seller.discount_value if v_seller else 0) + Decimal('250.00'), payment_method='full_pay', payment_ref='PM-ORD-2010', created_at=now, paid_at=now)
                db.session.add(o_s)
                db.session.commit()
                oi_s = OrderItem(order_id=o_s.id, product_id=sample_prod.id, quantity=1, unit_price=sample_prod.price, subtotal=sample_prod.price)
                db.session.add(oi_s)
                # apply voucher
                if v_seller:
                    o_s.voucher_id = v_seller.id
                    v_seller.uses_count = (v_seller.uses_count or 0) + 1
                db.session.add(v_seller)
                db.session.commit()

            # Create admin/seller activity: audit log and tickets
            try:
                al2 = AuditLog(actor_id=seller_v.id, actor_name=seller_v.full_name or seller_v.business_name, role='seller', action='demo_sale', module='seed', target_ref='ORD-2010', meta={'note': 'Sample seller sale for demo'})
                db.session.add(al2)
                ticket2 = InquiryTicket(ticket_ref='TCK-2002', customer_id=customer.id, order_id=o_s.id if sample_prod else None, assigned_to=seller_v.id, subject='Demo ticket for seller', description='Seller handling demo ticket', priority='low', status='open')
                db.session.add(ticket2)
                db.session.commit()
            except Exception:
                app.logger.exception('Could not create seller/admin demo activity; continuing')

            print('Extended demo scenarios seeded.')
        except Exception:
            app.logger.exception('Error seeding extended demo scenarios; continuing')

        # --- Add demo customers and populate reviews & stars for all products ---
        print('\n--- Seeding additional demo customers, reviews and stars for all products ---')
        try:
            try:
                from eacis.models.review import Review
                from eacis.models.product_star import ProductStar
            except Exception:
                from models.review import Review
                from models.product_star import ProductStar

            demo_customer_emails = [
                'alice@demo.com',
                'bob@demo.com',
                'carol@demo.com',
                'dave@demo.com',
                'erin@demo.com',
                'frank@demo.com',
            ]
            demo_customers = []
            for e in demo_customer_emails:
                u = User.query.filter_by(email=e).first()
                if not u:
                    u = User(email=e, role='customer', full_name=e.split('@')[0].title() + ' Demo', first_name=e.split('@')[0].title(), last_name='Demo', is_active=True, email_verified_at=now)
                    u.set_password('demo123')
                    db.session.add(u)
                    db.session.commit()
                demo_customers.append(u)

            # include existing seeded customers and reviewers
            known_customers = []
            existing_main = User.query.filter_by(email='customer@demo.com').first()
            if existing_main:
                known_customers.append(existing_main)
            for name in ('reviewer1@demo.com', 'reviewer2@demo.com', 'reviewer3@demo.com'):
                u = User.query.filter_by(email=name).first()
                if u:
                    known_customers.append(u)
            known_customers.extend(demo_customers)

            # Fetch all products (active ones) and add 2-3 reviews/stars each
            all_products = Product.query.order_by(Product.id).all()
            if not all_products:
                print('No products found to seed reviews for; skipping.')
            else:
                idx = 0
                for prod in all_products:
                    # pick up to 3 distinct customers per product by rotating through known_customers
                    reviewers = []
                    for j in range(3):
                        reviewers.append(known_customers[(idx + j) % len(known_customers)])
                    idx += 1

                    for u in reviewers:
                        try:
                            # Product star
                            existing_star = ProductStar.query.filter_by(product_id=prod.id, user_id=u.id).first()
                            if not existing_star:
                                ps = ProductStar(product_id=prod.id, user_id=u.id)
                                db.session.add(ps)

                            # Review (unique per product,user)
                            existing_review = Review.query.filter_by(product_id=prod.id, user_id=u.id).first()
                            if not existing_review:
                                rating = ((prod.id + u.id) % 5) + 1
                                title = f"{prod.name} - {rating} stars"
                                body = f"I purchased the {prod.name}. Works well for everyday use. — {u.first_name}"
                                r = Review(product_id=prod.id, user_id=u.id, rating=rating, title=title, body=body, reviewer_name=u.full_name, is_approved=True)
                                db.session.add(r)
                        except Exception:
                            app.logger.exception(f'Could not create star/review for product {prod.id} user {u.email}; skipping')

                db.session.commit()
                print('Added demo customers and reviews/stars for all products.')
        except Exception:
            app.logger.exception('Could not seed demo customers/reviews/stars; continuing')

        # Create dev-only fixed OTPs for seeded demo users (non-production only).
        try:
            if str(app.config.get('FLASK_ENV') or '').lower() != 'production':
                try:
                    from eacis.services.otp_service import _hash_code
                except Exception:
                    try:
                        from ..services.otp_service import _hash_code
                    except Exception:
                        from services.otp_service import _hash_code
                try:
                    from eacis.models.otp_challenge import OtpChallenge
                except Exception:
                    try:
                        from models.otp_challenge import OtpChallenge
                    except Exception:
                        OtpChallenge = None

                seed_emails = ['admin@eacis.com', 'seller@verified.com', 'seller@pending.com', 'customer@demo.com', 'reviewer1@demo.com', 'reviewer2@demo.com']
                try:
                    seed_emails.extend(demo_customer_emails)
                except Exception:
                    pass

                default_code = str(app.config.get('DEV_SEED_FIXED_OTP') or '123456')
                code_len = int(app.config.get('OTP_CODE_LENGTH') or 6)
                if len(default_code) >= code_len:
                    fixed_code = default_code[:code_len]
                else:
                    fixed_code = default_code + ('1' * (code_len - len(default_code)))

                expires = datetime.utcnow() + timedelta(days=3650)
                if OtpChallenge is not None:
                    for email in set(seed_emails):
                        try:
                            u = User.query.filter_by(email=email).first()
                            if not u:
                                continue
                            existing = OtpChallenge.query.filter_by(email=email, purpose='login').order_by(OtpChallenge.created_at.desc()).first()
                            if existing:
                                existing.code_hash = _hash_code(fixed_code)
                                existing.expires_at = expires
                                existing.meta = dict(existing.meta or {}, debug_code=fixed_code, dev_preview=True, seed_account=True)
                                db.session.add(existing)
                            else:
                                ch = OtpChallenge(user_id=u.id, email=email, purpose='login', code_hash=_hash_code(fixed_code), expires_at=expires, sent_to=email, meta={'debug_code': fixed_code, 'dev_preview': True, 'seed_account': True})
                                db.session.add(ch)
                        except Exception:
                            app.logger.exception('Failed to create fixed OTP for %s', email)
                    db.session.commit()
        except Exception:
            app.logger.exception('Failed to create fixed OTPs for seeded accounts')

        # Ensure all seeded accounts are email-verified (development convenience)
        try:
            now_verify = datetime.utcnow()
            # If an earlier DB flush failed the transaction, ensure we rollback
            try:
                db.session.rollback()
            except Exception:
                pass
            all_users = User.query.all()
            for u in all_users:
                if not getattr(u, 'email_verified_at', None):
                    try:
                        u.email_verified_at = now_verify
                        db.session.add(u)
                    except Exception:
                        app.logger.exception('Could not set email_verified_at for user %s', getattr(u, 'email', None))
            db.session.commit()
            print('All seeded users marked as email-verified.')
        except Exception:
            app.logger.exception('Failed to mark seeded users as email-verified')

if __name__ == "__main__":
    seed_database()
