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

class LoyaltyTransaction(db.Model):
    __tablename__ = 'loyalty_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.Enum('earn','redeem','expire','adjust', name='loyalty_type'))
    points = db.Column(db.Integer)
    reference = db.Column(db.String(100))
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
