try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_ref = db.Column(db.String(30), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.Enum('pending','paid','packed','shipped','delivered','past_due','refunded','cancelled', name='order_status'))
    subtotal = db.Column(db.Numeric(12,2))
    discount = db.Column(db.Numeric(12,2), default=0)
    shipping_fee = db.Column(db.Numeric(12,2), default=0)
    tax = db.Column(db.Numeric(12,2), default=0)
    total = db.Column(db.Numeric(12,2))
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'), nullable=True)
    loyalty_redeemed = db.Column(db.Integer, default=0)
    payment_method = db.Column(db.Enum('full_pay','installment', name='payment_method'))
    payment_ref = db.Column(db.String(100))
    shipping_address = db.Column(db.JSON)
    tracking_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)

    items = db.relationship('OrderItem', backref='order', lazy='dynamic')

    def __repr__(self):
        return f"<Order {self.order_ref} - {self.status}>"

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer)
    unit_price = db.Column(db.Numeric(12,2))
    subtotal = db.Column(db.Numeric(12,2))

    product = db.relationship('Product')
