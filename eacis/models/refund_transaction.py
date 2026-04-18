try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timezone


class RefundTransaction(db.Model):
    __tablename__ = 'refund_transactions'

    id = db.Column(db.Integer, primary_key=True)
    refund_ref = db.Column(db.String(30), unique=True, nullable=False)
    return_request_id = db.Column(db.Integer, db.ForeignKey('return_requests.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.Enum('requested', 'processed', 'failed', name='refund_status'), default='requested')
    method = db.Column(db.String(50), default='original_payment_method')
    processed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    return_request = db.relationship('ReturnRequest', backref='refund_transactions')

    def __repr__(self):
        return f"<RefundTransaction {self.refund_ref}>"
