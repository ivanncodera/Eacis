import sys, os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.product import Product
from eacis.models.user import User

app = create_app()

with app.app_context():
    print(f"Users in DB: {User.query.count()}")
    print(f"Products in DB: {Product.query.count()}")
    print('\nSample products:')
    for p in Product.query.order_by(Product.id).all():
        print(f"- {p.product_ref} | {p.name} | {p.category} | {p.price} | image={p.image_url}")
