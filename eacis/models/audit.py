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

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    actor_name = db.Column(db.String(255))
    role = db.Column(db.String(50))
    action = db.Column(db.String(100))
    module = db.Column(db.String(50))
    target_ref = db.Column(db.String(100))
    meta = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
