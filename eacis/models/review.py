try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timezone


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.SmallInteger, nullable=False)
    title = db.Column(db.String(255))
    body = db.Column(db.Text)
    is_approved = db.Column(db.Boolean, default=True)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    reviewer_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('product_id', 'user_id', name='uix_product_user_review'),
    )

    def __repr__(self):
        return f"<Review {self.id} p:{self.product_id} u:{self.user_id} r:{self.rating}>"
