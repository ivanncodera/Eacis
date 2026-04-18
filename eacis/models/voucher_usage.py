try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timezone


class VoucherUsageLog(db.Model):
    """
    Per-order, per-customer voucher usage audit trail.

    Why this exists:
    The Voucher model has uses_count (a running counter) and
    Order has voucher_id.  But neither gives you a fast answer to
    "how many times has customer X used voucher Y across all orders?"
    without joining three tables.  This table makes that O(1).

    It also provides the transactional safety net: even if a race
    condition incremented uses_count twice, the log will show two rows,
    making the inconsistency detectable and auditable.
    """
    __tablename__ = 'voucher_usage_logs'
    __table_args__ = {'extend_existing': True}

    id                = db.Column(db.Integer, primary_key=True)
    voucher_id        = db.Column(db.Integer, db.ForeignKey('vouchers.id'), nullable=False, index=True)
    customer_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_id          = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    discount_applied  = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    used_at           = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    voucher  = db.relationship('Voucher', backref=db.backref('usage_logs', lazy='dynamic'))
    customer = db.relationship('User', foreign_keys=[customer_id])
    order    = db.relationship('Order', foreign_keys=[order_id])

    def __repr__(self):
        return f'<VoucherUsageLog voucher={self.voucher_id} customer={self.customer_id} order={self.order_id}>'
