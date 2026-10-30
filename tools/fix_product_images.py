import os
import sys
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.product import Product

app = create_app()

def pick_asset_for_product_name(name, category, available):
    n = re.sub(r"[^a-z0-9 ]", ' ', name.lower())
    words = set(n.split())

    for asset in available:
        base = os.path.splitext(asset)[0].lower()
        parts = set(re.sub(r"[^a-z0-9 ]", ' ', base).split())
        if parts & words:
            return asset

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

    return available[0] if available else None

with app.app_context():
    assets_dir = os.path.join(app.root_path, 'static', 'assets', 'products')
    if not os.path.isdir(assets_dir):
        print('No assets directory found at', assets_dir)
        sys.exit(1)

    available = [f for f in sorted(os.listdir(assets_dir)) if os.path.isfile(os.path.join(assets_dir, f)) and f.lower().endswith(('.jpg','.jpeg','.png','.webp','.jfif'))]
    if not available:
        print('No image assets found in', assets_dir)
        sys.exit(1)

    updated = 0
    for p in Product.query.order_by(Product.id).all():
        chosen = pick_asset_for_product_name(p.name, p.category, available)
        if chosen:
            new_url = f"/static/assets/products/{chosen}"
            if p.image_url != new_url:
                p.image_url = new_url
                db.session.add(p)
                updated += 1

    if updated:
        db.session.commit()

    print(f'Updated image_url for {updated} products (set to static assets mapping).')
