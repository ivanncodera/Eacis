import pytest

from eacis.app import create_app, db
from eacis.config import Config
from eacis.models.otp_challenge import OtpChallenge
from eacis.models.audit import AuditLog
from eacis.models.user import User


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_ENABLED = False
    FLASK_ENV = 'development'
    SECRET_KEY = 'test-secret'


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_registration_sends_activation_link_and_requires_verification(app, client):
    # Submit registration form with required customer fields
    resp = client.post('/auth/register/customer', data={
        'first_name': 'New',
        'middle_name': '',
        'last_name': 'User',
        'address_line1': '123 Test St',
        'barangay': 'Barangay 1',
        'city_municipality': 'Quezon City',
        'province': 'Metro Manila',
        'postal_code': '1100',
        'phone': '09171234567',
        'email': 'newuser@example.com',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'terms_consent': '1',
        'privacy_consent': '1',
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b'Verify' in resp.data or b'verify' in resp.data

    # find the most recent register_verify challenge for this email
    chal = OtpChallenge.query.filter_by(email='newuser@example.com', purpose='register_verify').order_by(OtpChallenge.created_at.desc()).first()
    assert chal is not None
    token = (chal.meta or {}).get('activation_token')
    assert token

    # login should be blocked before verification
    resp2 = client.post('/auth/login', data={'email': 'newuser@example.com', 'password': 'Password123!'}, follow_redirects=True)
    assert resp2.status_code == 200
    assert b'Verify' in resp2.data or b'verify' in resp2.data

    # Activate token via one-click link
    resp3 = client.get(f'/auth/register/verify/{token}', follow_redirects=True)
    assert resp3.status_code == 200

    user = User.query.filter_by(email='newuser@example.com').first()
    assert user is not None
    assert user.email_verified_at is not None

    al = AuditLog.query.filter_by(action='email_verified', target_ref='newuser@example.com').order_by(AuditLog.created_at.desc()).first()
    assert al is not None
