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

class Voucher(db.Model):
    __tablename__ = 'vouchers'
    id = db.Column(db.Integer, primary_key=True)
    voucher_ref = db.Column(db.String(30), unique=True)
    code = db.Column(db.String(50), unique=True)
    discount_type = db.Column(db.Enum('percent','fixed', name='voucher_type'))
    discount_value = db.Column(db.Numeric(10,2))
    min_order_amount = db.Column(db.Numeric(12,2), default=0)
    max_uses = db.Column(db.Integer)
    uses_count = db.Column(db.Integer, default=0)
    per_user_limit = db.Column(db.Integer, default=1)
    valid_from = db.Column(db.DateTime)
    valid_until = db.Column(db.DateTime)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    combinable = db.Column(db.Boolean, default=False)

    def is_valid(self):
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from: return False
        if self.valid_until and now > self.valid_until: return False
        return self.is_active
