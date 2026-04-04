import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eacis.app import create_app
from eacis.models.user import User
from eacis.models.product import Product

app = create_app()
with app.app_context():
    print('Users:', User.query.count())
    print('Products:', Product.query.count())
    u = User.query.filter_by(email='customer@eacis.ph').first()
    print('Customer exists:', bool(u))
