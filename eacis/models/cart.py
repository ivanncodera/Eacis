try:
    from ..app import db
except Exception:
    try:
        from eacis.extensions import db
    except Exception:
        try:
            from ..extensions import db
        except Exception:
            from extensions import db
from datetime import datetime

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    items = db.Column(db.JSON)  # list of {product_id, qty}
    voucher_code = db.Column(db.String(50))
    loyalty_redeemed = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
