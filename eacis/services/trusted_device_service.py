"""
Trusted device helpers: create tokens, verify, revoke, touch.
"""
from datetime import datetime, timedelta
import hashlib
import secrets

from flask import current_app

try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db

try:
    from eacis.models.trusted_device import TrustedDevice
except Exception:
    try:
        from ..models.trusted_device import TrustedDevice
    except Exception:
        from models.trusted_device import TrustedDevice

try:
    from eacis.models.user import User
except Exception:
    try:
        from ..models.user import User
    except Exception:
        from models.user import User


def _hash_token(token):
    pepper = str(current_app.config.get('OTP_SECRET_PEPPER') or '')
    raw = f'{pepper}:{token}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def create_trusted_device(user_id, device_name=None, days_valid=30):
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.utcnow() + timedelta(days=days_valid)
    td = TrustedDevice(
        user_id=user_id,
        token_hash=token_hash,
        device_name=(device_name or '')[:255],
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow(),
        expires_at=expires_at,
        revoked=False,
    )
    db.session.add(td)
    db.session.commit()
    return token, td


def find_by_token(token):
    token_hash = _hash_token(token)
    td = TrustedDevice.query.filter_by(token_hash=token_hash, revoked=False).first()
    if not td:
        return None
    if td.expires_at and td.expires_at < datetime.utcnow():
        return None
    return td


def touch(td):
    td.last_used_at = datetime.utcnow()
    db.session.commit()


def revoke(td):
    td.revoked = True
    db.session.commit()


def list_trusted_devices(user_id):
    try:
        return TrustedDevice.query.filter_by(user_id=user_id).order_by(TrustedDevice.created_at.desc()).all()
    except Exception:
        return []


def revoke_by_id(user_id, td_id):
    try:
        td = TrustedDevice.query.filter_by(id=int(td_id), user_id=user_id).first()
    except Exception:
        return False
    if not td:
        return False
    td.revoked = True
    db.session.commit()
    return True


def list_all_trusted_devices(search_email=None, limit=200):
    try:
        q = db.session.query(TrustedDevice, User).join(User, TrustedDevice.user_id == User.id)
        if search_email:
            q = q.filter(User.email.ilike(f"%{search_email}%"))
        rows = q.order_by(TrustedDevice.created_at.desc()).limit(int(limit)).all()
        results = []
        for td, user in rows:
            results.append({'device': td, 'user_email': getattr(user, 'email', None), 'user_id': getattr(user, 'id', None)})
        return results
    except Exception:
        return []


def revoke_admin_by_id(td_id):
    try:
        td = TrustedDevice.query.get(int(td_id))
    except Exception:
        return False
    if not td:
        return False
    td.revoked = True
    db.session.commit()
    return True
