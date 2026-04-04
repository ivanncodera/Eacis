import sys, os

# Make package importable when executing directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from models.user import User
from models.product import Product

app = create_app()

def fmt_price(p):
    try:
        return f"{p:,.2f}"
    except Exception:
        return str(p)

with app.app_context():
    ucount = User.query.count()
    pcount = Product.query.count()
    print(f"Users in DB: {ucount}")
    print(f"Products in DB: {pcount}")

    print('\nSample users:')
    for u in User.query.limit(5).all():
        print(f"- {u.id}: {u.email} ({u.role}) full_name={getattr(u,'full_name',None)}")

    print('\nSample products:')
    for p in Product.query.limit(10).all():
        print(f"- {p.id}: {p.product_ref} | {p.name} | {fmt_price(p.price)} | image={p.image_url} | seller_id={p.seller_id}")

    # validate one image file exists locally
    if pcount:
        sample = Product.query.first()
        static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', sample.image_url))
        exists = os.path.exists(static_path)
        print(f"\nImage file for first product exists on disk: {exists} -> {static_path}")
