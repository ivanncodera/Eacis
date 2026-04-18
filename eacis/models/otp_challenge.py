try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime, timezone


class OtpChallenge(db.Model):
    __tablename__ = 'otp_challenges'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(50), nullable=False)  # login/register/password_reset/etc.

    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime, nullable=True)

    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=5, nullable=False)

    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    sent_to = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    verified_at = db.Column(db.DateTime, nullable=True)
    failure_reason = db.Column(db.String(100), nullable=True)
    meta = db.Column(db.JSON, nullable=True)

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_expired(self):
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if not expires:
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires

    def __repr__(self):
        return f"<OtpChallenge {self.id} {self.purpose} {self.email}>"
