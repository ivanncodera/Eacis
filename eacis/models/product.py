try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    product_ref = db.Column(db.String(30), unique=True, nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12,2), nullable=False)
    compare_price = db.Column(db.Numeric(12,2))
    stock = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=5)
    warranty_months = db.Column(db.Integer, default=12)
    installment_enabled = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    weight_kg = db.Column(db.Numeric(6,2))
    image_url = db.Column(db.String(500))
    specs = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold

    def __repr__(self):
        return f"<Product {self.product_ref} - {self.name}>"
