try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('customer','seller','admin', name='user_roles'), nullable=False)
    full_name = db.Column(db.String(255))
    first_name = db.Column(db.String(100))
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    suffix = db.Column(db.String(20))

    address_line1 = db.Column(db.String(255))
    address_line2 = db.Column(db.String(255))
    barangay = db.Column(db.String(120))
    city_municipality = db.Column(db.String(120))
    province = db.Column(db.String(120))
    region = db.Column(db.String(120))
    postal_code = db.Column(db.String(20))

    business_name = db.Column(db.String(255))
    business_permit_path = db.Column(db.String(500))
    barangay_permit_path = db.Column(db.String(500))
    mayors_permit_path = db.Column(db.String(500))
    seller_verification_status = db.Column(db.String(20), default='pending')
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    loyalty_points = db.Column(db.Integer, default=0)
    seller_code = db.Column(db.String(10), unique=True, nullable=True)

    products = db.relationship('Product', backref='seller', lazy='dynamic')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    addresses = db.relationship('Address', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def computed_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name, self.suffix]
        normalized = [str(part).strip() for part in parts if part and str(part).strip()]
        if normalized:
            return ' '.join(normalized)
        return (self.full_name or '').strip()

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
