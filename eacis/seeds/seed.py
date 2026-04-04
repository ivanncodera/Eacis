import sys, os

# Ensure project package is importable when running this script directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db
from models.user import User
from models.product import Product
from pathlib import Path
from decimal import Decimal

app = create_app()

KITCHEN_PRODUCTS = [
    ("PRD-SLR01-0001", "Two-Door Refrigerator (10 cu. ft.)", "Kitchen & Cooking", 18000, 12, 12, True, "Inverter", "2-door-refrigirator.webp"),
    ("PRD-SLR01-0002", "Single Door Refrigerator (6 cu. ft.)", "Kitchen & Cooking", 8500, 20, 12, True, None, "single-door-ref.webp"),
    ("PRD-SLR01-0003", "Inverter Chest Freezer", "Kitchen & Cooking", 11000, 8, 12, True, "Inverter", "inverted-chest-freezer.webp"),
    ("PRD-SLR01-0004", "Gas Range with Oven (4 Burners)", "Kitchen & Cooking", 14500, 6, 12, True, "New", "gas-range-with-oven-4-burners.webp"),
    ("PRD-SLR01-0005", "Induction Cooker (Double Zone)", "Kitchen & Cooking", 4500, 30, 6, False, None, "induction-cooker-double.png"),
    ("PRD-SLR01-0006", "Single Burner Induction Cooker", "Kitchen & Cooking", 1800, 50, 0, False, None, "single-burner-induction-cooker.webp"),
    ("PRD-SLR01-0007", "Microwave Oven (20L)", "Kitchen & Cooking", 3200, 25, 0, False, None, "microwave-oven.jfif"),
    ("PRD-SLR01-0008", "Air Fryer (5L)", "Kitchen & Cooking", 2800, 40, 0, False, None, "air-fryer.jfif"),
    ("PRD-SLR01-0009", "Electric Oven/Rotisserie (35L)", "Kitchen & Cooking", 4000, 10, 0, False, None, "electric-oven-rotisserie.webp"),
    ("PRD-SLR01-0010", "Rice Cooker (1.8L)", "Kitchen & Cooking", 1500, 60, 0, False, None, "rice-cooker.jpg"),
    ("PRD-SLR01-0011", "Electric Kettle (1.7L)", "Kitchen & Cooking", 800, 80, 0, False, None, "electric-kettle.webp"),
    ("PRD-SLR01-0012", "Stand Mixer", "Kitchen & Cooking", 4500, 15, 0, False, None, "stand-mixer.jfif"),
    ("PRD-SLR01-0013", "Electric Food Processor", "Kitchen & Cooking", 2200, 20, 0, False, None, "electric-food-processor.jfif"),
    ("PRD-SLR01-0014", "Blender (1.5L)", "Kitchen & Cooking", 1600, 25, 0, False, None, "blender.jfif"),
    ("PRD-SLR01-0015", "Coffee Maker (Drip type)", "Kitchen & Cooking", 1200, 30, 0, False, None, "coffee-maker.jfif"),
    ("PRD-SLR01-0016", "Espresso Machine (Home Entry-level)", "Kitchen & Cooking", 6500, 8, 0, False, None, "espresso-machine.jfif"),
    ("PRD-SLR01-0017", "Bread Toaster (2-Slice)", "Kitchen & Cooking", 900, 40, 0, False, None, "bread-toaster.jfif"),
    ("PRD-SLR01-0018", "Sandwich Maker/Waffle Iron", "Kitchen & Cooking", 1100, 35, 0, False, None, "sandwich-maker.jfif"),
    ("PRD-SLR01-0019", "Juice Extractor", "Kitchen & Cooking", 2500, 20, 0, False, None, "juice-extractor.jfif"),
    ("PRD-SLR01-0020", "Slow Cooker (3.5L)", "Kitchen & Cooking", 1800, 22, 0, False, None, "slow-cooker.jfif"),
    ("PRD-SLR01-0021", "Dishwasher (Countertop)", "Kitchen & Cooking", 12000, 6, 0, False, None, "dishwasher-countertop.jfif"),
    ("PRD-SLR01-0022", "Water Dispenser (Top Load)", "Kitchen & Cooking", 3500, 18, 0, False, None, "water-dispenser.webp")
]

with app.app_context():
    db.create_all()

    if User.query.filter_by(email='customer@eacis.ph').first():
        print('Seed looks already applied — exiting')
    else:
        # create users
        customer = User(email='customer@eacis.ph', role='customer', full_name='Juan dela Cruz', loyalty_points=240)
        customer.set_password('customer123')
        seller = User(email='seller@eacis.ph', role='seller', full_name='Maria Santos', seller_code='SLR01')
        seller.set_password('seller123')
        admin = User(email='admin@eacis.ph', role='admin', full_name='Admin User')
        admin.set_password('admin123')
        db.session.add_all([customer, seller, admin])
        db.session.commit()

        # add products tied to seller
        for p in KITCHEN_PRODUCTS:
            ref, name, cat, price, stock, warranty, installment, badge, img = p
            prod = Product(
                product_ref=ref,
                seller_id=seller.id,
                name=name,
                category=cat,
                price=Decimal(price),
                stock=stock,
                warranty_months=warranty,
                installment_enabled=installment,
                image_url=f"assets/products/{img}"
            )
            db.session.add(prod)
        db.session.commit()
        print('Seed completed: users + kitchen products')
