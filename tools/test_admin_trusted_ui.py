import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eacis.app import create_app, db
from eacis.config import Config
from eacis.models.user import User
from eacis.models.trusted_device import TrustedDevice
from eacis.services.trusted_device_service import create_trusted_device


class SmokeAdminConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TESTING = True
    WTF_CSRF_ENABLED = False
    MAIL_ENABLED = False
    USE_DEV_SEEDS = False


def run_admin_ui_smoke():
    app = create_app(SmokeAdminConfig)
    with app.app_context():
        db.create_all()
        admin = User(email='admin@eacis.test', role='admin', full_name='Admin Test')
        admin.set_password('adminpass')
        user = User(email='cust@eacis.test', role='customer', full_name='Customer Test')
        user.set_password('custpass')
        db.session.add(admin)
        db.session.add(user)
        db.session.commit()

        # create trusted devices
        token1, td1 = create_trusted_device(user.id, device_name='Test Device 1', days_valid=30)
        token2, td2 = create_trusted_device(admin.id, device_name='Admin Device', days_valid=30)

        client = app.test_client()
        # mark session as logged in admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        r = client.get('/admin/trusted-devices')
        if r.status_code != 200:
            print('FAIL: GET /admin/trusted-devices returned', r.status_code)
            return 1

        # Revoke a device via POST
        post = client.post('/admin/trusted-devices', data={'revoke_id': td1.id}, follow_redirects=True)
        if post.status_code != 200:
            print('FAIL: POST revoke returned', post.status_code)
            return 1

        with app.app_context():
            refreshed = TrustedDevice.query.get(td1.id)
            if not refreshed or not refreshed.revoked:
                print('FAIL: Device was not revoked in DB')
                return 1

    print('PASS admin trusted-devices UI smoke')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_admin_ui_smoke())
