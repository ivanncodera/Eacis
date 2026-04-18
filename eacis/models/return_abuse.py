try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timezone


class ReturnAbuseLog(db.Model):
    """
    Per-customer rolling abuse score for the return/refund feature.

    Score formula (computed every time a return or refund event fires):
      +2 per return submitted in last RETURN_ABUSE_WINDOW_DAYS days
      +3 per CHANGED_MIND return in window
      +5 per refund amount / avg_order_value ratio point (capped per event)
      -1 per completed order with NO return in window (good-faith purchaser)

    Thresholds (see Config):
      score >= RETURN_ABUSE_FLAG_THRESHOLD     (default 10) → is_flagged = True
      score >= RETURN_ABUSE_RESTRICT_THRESHOLD (default 20) → is_restricted = True
        (blocks new return submissions until admin reviews)

    The score is recomputed from raw transaction data; this row is a cache
    that also stores the human-readable flag_reason for admin review.
    """
    __tablename__ = 'return_abuse_logs'

    id            = db.Column(db.Integer, primary_key=True)
    customer_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    abuse_score   = db.Column(db.Float, default=0.0, nullable=False)
    flag_reason   = db.Column(db.Text)           # human-readable summary for admin
    is_flagged    = db.Column(db.Boolean, default=False, nullable=False)
    is_restricted = db.Column(db.Boolean, default=False, nullable=False)  # blocks submissions
    last_computed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Admin review fields
    reviewed_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at   = db.Column(db.DateTime, nullable=True)
    admin_notes   = db.Column(db.Text)

    customer  = db.relationship('User', foreign_keys=[customer_id], backref='abuse_log')
    reviewer  = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        flag = ' [FLAGGED]' if self.is_flagged else ''
        restr = ' [RESTRICTED]' if self.is_restricted else ''
        return f'<ReturnAbuseLog customer={self.customer_id} score={self.abuse_score:.1f}{flag}{restr}>'
