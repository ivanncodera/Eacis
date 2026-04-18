import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eacis.app import create_app, db
from eacis.config import Config
from eacis.models.otp_challenge import OtpChallenge
from eacis.models.user import User
from eacis.services.otp_service import create_and_send_otp, verify_otp


class SmokeConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TESTING = True
    WTF_CSRF_ENABLED = True
    MAIL_ENABLED = False
    USE_DEV_SEEDS = False


def _csrf_token(html):
    match = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _debug_code(html):
    match = re.search(r'Development preview code:\s*([0-9]{6})', html)
    return match.group(1) if match else None


def _latest_debug_code(app, email, purpose):
    with app.app_context():
        challenge = (
            OtpChallenge.query
            .filter_by(email=email, purpose=purpose)
            .order_by(OtpChallenge.created_at.desc())
            .first()
        )
        if not challenge or not challenge.meta or not isinstance(challenge.meta, dict):
            return None
        return challenge.meta.get('debug_code')


def _seed_customer(app):
    with app.app_context():
        db.create_all()
        customer = User(
            email='customer@eacis.ph',
            role='customer',
            full_name='Juan dela Cruz',
            first_name='Juan',
            last_name='dela Cruz',
            phone='09171234567',
            address_line1='123 Test Street',
            barangay='Test Barangay',
            city_municipality='Quezon City',
            province='Metro Manila',
            region='NCR',
            postal_code='1100',
        )
        customer.set_password('customer123')
        db.session.add(customer)
        db.session.commit()
        return {
            'email': customer.email,
            'first_name': customer.first_name,
            'middle_name': customer.middle_name,
            'last_name': customer.last_name,
            'suffix': customer.suffix,
            'phone': customer.phone,
            'address_line1': customer.address_line1,
            'address_line2': customer.address_line2,
            'barangay': customer.barangay,
            'city_municipality': customer.city_municipality,
            'province': customer.province,
            'region': customer.region,
            'postal_code': customer.postal_code,
        }


def run_otp_smoke_tests():
    app = create_app(SmokeConfig)
    failures = []

    customer = _seed_customer(app)

    # Service-level OTP behavior.
    with app.app_context():
        unique_email = f'otp-smoke-{os.getpid()}@example.com'

        challenge, message = create_and_send_otp(unique_email, 'login', user_id=None, meta={'suite': 'otp_smoke'})
        if not challenge:
            failures.append(f'OTP create failed: {message}')
        else:
            if challenge.meta.get('debug_code') is None:
                failures.append('Dev preview OTP code was not stored in metadata')

            ok, ok_message = verify_otp(challenge.id, challenge.meta.get('debug_code'))
            if not ok:
                failures.append(f'OTP verify failed for fresh code: {ok_message}')

            wrong, wrong_message = verify_otp(challenge.id, '000000')
            if wrong:
                failures.append('OTP verify unexpectedly accepted an invalid code')
            elif 'already been used' not in wrong_message.lower() and 'invalid' not in wrong_message.lower():
                failures.append(f'Unexpected invalid-code message: {wrong_message}')

        resend_a, resend_message_a = create_and_send_otp(unique_email, 'password_reset', user_id=None)
        resend_b, resend_message_b = create_and_send_otp(unique_email, 'password_reset', user_id=None)
        if not resend_a:
            failures.append(f'OTP resend baseline failed: {resend_message_a}')
        if resend_b is not None:
            failures.append('OTP resend cooldown did not block a repeated request')

        expired_challenge, expired_message = create_and_send_otp(f'expired-{os.getpid()}@example.com', 'step_up', user_id=None)
        if not expired_challenge:
            failures.append(f'Expired-OTP setup failed: {expired_message}')
        else:
            expired_challenge.expires_at = expired_challenge.created_at
            db.session.commit()
            expired_ok, expired_ok_message = verify_otp(expired_challenge.id, expired_challenge.meta.get('debug_code'))
            if expired_ok:
                failures.append('Expired OTP was accepted')
            elif 'expired' not in expired_ok_message.lower():
                failures.append(f'Unexpected expired-code message: {expired_ok_message}')

    # Route-level login step-up and email change verification.
    client = app.test_client()
    login_page = client.get('/auth/login')
    if login_page.status_code != 200:
        failures.append(f'GET /auth/login expected 200, got {login_page.status_code}')
    else:
        login_csrf = _csrf_token(login_page.get_data(as_text=True))
        login_response = client.post(
            '/auth/login',
            data={'email': 'customer@eacis.ph', 'password': 'customer123', 'csrf_token': login_csrf},
            follow_redirects=False,
        )
        if login_response.status_code not in (301, 302, 303):
            failures.append(f'Login step-up expected redirect, got {login_response.status_code}')
        login_code = _latest_debug_code(app, 'customer@eacis.ph', 'register_verify') or _latest_debug_code(app, 'customer@eacis.ph', 'login')
        if not login_code:
            failures.append('Login OTP challenge did not expose a development preview code')
        else:
            otp_page = client.get('/auth/otp/verify')
            otp_html = otp_page.get_data(as_text=True)
            otp_csrf = _csrf_token(otp_html)
            verify_response = client.post(
                '/auth/otp/verify',
                data={'otp_code': login_code, 'csrf_token': otp_csrf},
                follow_redirects=False,
            )
            if verify_response.status_code not in (301, 302, 303):
                failures.append(f'Login OTP verify expected redirect, got {verify_response.status_code}')

        profile_page = client.get('/customer/profile/edit')
        if profile_page.status_code != 200:
            failures.append(f'GET /customer/profile/edit expected 200, got {profile_page.status_code}')
        else:
            profile_html = profile_page.get_data(as_text=True)
            profile_csrf = _csrf_token(profile_html)
            new_email = f'otp-change-{os.getpid()}@example.com'
            profile_payload = {
                'csrf_token': profile_csrf,
                'first_name': customer['first_name'] or 'Juan',
                'middle_name': customer['middle_name'] or '',
                'last_name': customer['last_name'] or 'Dela Cruz',
                'suffix': customer['suffix'] or '',
                'email': new_email,
                'phone': customer['phone'] or '09171234567',
                'address_line1': customer['address_line1'] or '123 Test Street',
                'address_line2': customer['address_line2'] or '',
                'barangay': customer['barangay'] or 'Test Barangay',
                'city_municipality': customer['city_municipality'] or 'Quezon City',
                'province': customer['province'] or 'Metro Manila',
                'region': customer['region'] or 'NCR',
                'postal_code': customer['postal_code'] or '1100',
                'current_password': 'customer123',
                'terms_consent': 'yes',
                'privacy_consent': 'yes',
            }
            profile_response = client.post('/customer/profile/edit', data=profile_payload, follow_redirects=False)
            if profile_response.status_code not in (301, 302, 303):
                failures.append(f'Profile email change expected redirect, got {profile_response.status_code}')
            change_code = _latest_debug_code(app, new_email.lower(), 'email_change') or _latest_debug_code(app, 'customer@eacis.ph', 'email_change')
            if not change_code:
                failures.append('Email change OTP challenge did not expose a development preview code')
            else:
                profile_otp_page = client.get('/auth/otp/verify')
                profile_otp_html = profile_otp_page.get_data(as_text=True)
                change_csrf = _csrf_token(profile_otp_html)
                change_verify = client.post(
                    '/auth/otp/verify',
                    data={'otp_code': change_code, 'csrf_token': change_csrf},
                    follow_redirects=False,
                )
                if change_verify.status_code not in (301, 302, 303):
                    failures.append(f'Email change OTP verify expected redirect, got {change_verify.status_code}')

                with app.app_context():
                    updated = User.query.filter_by(email=new_email).first()
                    if not updated:
                        failures.append('Email change OTP flow did not update the user email')
                    else:
                        updated.email = 'customer@eacis.ph'
                        updated.email_verified_at = None
                        db.session.commit()

    # Phase 4 and protection hooks must remain wired in the source.
    source = (ROOT / 'eacis' / 'app.py').read_text(encoding='utf-8')
    expected_purposes = [
        "purpose='installment_confirm'",
        "purpose='order_cancel'",
        "purpose='seller_refund'",
        "purpose='admin_action'",
        "purpose='email_change'",
        "purpose='seller_security'",
    ]
    for needle in expected_purposes:
        if needle not in source:
            failures.append(f'Missing OTP purpose wiring in app.py: {needle}')

    if failures:
        print('FAIL OTP smoke tests')
        for failure in failures:
            print('-', failure)
        return 1

    print('PASS OTP smoke tests')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_otp_smoke_tests())