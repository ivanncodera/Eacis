try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timedelta


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    invoice_ref = db.Column(db.String(30), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    subtotal = db.Column(db.Numeric(12, 2), default=0)
    discount_total = db.Column(db.Numeric(12, 2), default=0)
    tax_total = db.Column(db.Numeric(12, 2), default=0)
    shipping_total = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), default=0)

    status = db.Column(db.Enum('issued', 'paid', 'void', name='invoice_status'), default='issued')
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=7))

    order = db.relationship('Order', backref='invoices')
    customer = db.relationship('User', foreign_keys=[customer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])

    def __repr__(self):
        return f"<Invoice {self.invoice_ref}>"
