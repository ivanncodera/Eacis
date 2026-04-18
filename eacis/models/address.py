try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timezone


class Address(db.Model):
    __tablename__ = 'addresses'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    label = db.Column(db.String(50), nullable=True)
    recipient_name = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255), nullable=True)
    barangay = db.Column(db.String(120), nullable=True)
    city_municipality = db.Column(db.String(120), nullable=True)
    province = db.Column(db.String(120), nullable=True)
    region = db.Column(db.String(120), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def summary(self):
        parts = [self.address_line1, self.address_line2, self.barangay, self.city_municipality, self.province, self.region]
        return ', '.join([p for p in parts if p])
