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

class ReturnRequest(db.Model):
    __tablename__ = 'return_requests'
    id = db.Column(db.Integer, primary_key=True)
    rrt_ref = db.Column(db.String(30), unique=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    order = db.relationship('Order')
    customer = db.relationship('User')
    reason = db.Column(db.String(255))
    description = db.Column(db.Text)
    evidence_urls = db.Column(db.JSON)
    status = db.Column(db.Enum('pending','accepted','rejected','refund_requested','refunded', name='rrt_status'))
    seller_notes = db.Column(db.Text)
    restocked_qty = db.Column(db.Integer)
    refund_amount = db.Column(db.Numeric(12,2))
    admin_notes = db.Column(db.Text)
    paymongo_refund_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
