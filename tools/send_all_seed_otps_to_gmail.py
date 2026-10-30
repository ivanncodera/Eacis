"""Send one OTP per seeded user to a target mailbox for demo inspection.

This script:
- Creates a real OtpChallenge for each user (purpose 'register_verify')
- Stores the plain OTP in `meta['debug_code']` so you can verify it on the site
- Sends the OTP email to the target mailbox using the configured SMTP backend

Usage: run from project root (virtualenv activated):
    python -m tools.send_all_seed_otps_to_gmail

Be careful: this will send live emails using the SMTP credentials in `eacis/.env`.
"""

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.user import User
from eacis.models.otp_challenge import OtpChallenge
from eacis.services.email_service import EmailService
from eacis.services.otp_service import _generate_code, _hash_code
from flask import current_app
from datetime import datetime, timedelta, timezone
import secrets
import logging

TARGET_EMAIL = 'codera.ivannbsis2023@gmail.com'

app = create_app()

def send_all():
    with app.app_context():
        app.logger.setLevel(logging.INFO)
        # ensure handlers show on console
        for h in app.logger.handlers:
            h.setLevel(logging.INFO)

        ttl = int(current_app.config.get('OTP_TTL_SECONDS') or 300)
        length = int(current_app.config.get('OTP_CODE_LENGTH') or 6)
        max_attempts = int(current_app.config.get('OTP_MAX_ATTEMPTS') or 5)

        users = User.query.order_by(User.id).all()
        print(f'Found {len(users)} users; sending OTP for each to {TARGET_EMAIL}')

        sent_ok = []
        sent_fail = []

        for u in users:
            try:
                code = _generate_code(length)
                token = secrets.token_urlsafe(24)
                code_hash = _hash_code(code)
                expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)

                chal = OtpChallenge(
                    user_id=u.id,
                    email=u.email,
                    purpose='register_verify',
                    code_hash=code_hash,
                    expires_at=expires,
                    max_attempts=max_attempts,
                    ip_address='127.0.0.1',
                    user_agent='seed-otp-script',
                    sent_to=TARGET_EMAIL,
                    meta={'debug_code': code, 'activation_token': token}
                )
                db.session.add(chal)
                db.session.commit()

                subject = f'E-ACIS Security Code (Register Verify)'
                text_body = (
                    f'Account: {u.email}\n'
                    f'Your E-ACIS verification code is: {code}\n\n'
                    f'This code expires in {ttl//60} minutes.\n'
                    f'If you did not request this, ignore this email.'
                )
                html_body = (
                    '<div style="font-family:Arial,sans-serif;line-height:1.6">'
                    '<h2>E-ACIS Security Verification</h2>'
                    f'<p>Account: <strong>{u.email}</strong></p>'
                    f'<p>Your one-time code is:</p><p style="font-size:28px;font-weight:700;letter-spacing:3px">{code}</p>'
                    f'<p>This code expires in <strong>{ttl//60} minutes</strong>.</p>'
                    '<p>If you did not request this code, please ignore this message.</p>'
                    '</div>'
                )

                ok, msg = EmailService.send_email(TARGET_EMAIL, subject, text_body, html_body=html_body)
                if ok:
                    print(f'SENT -> {u.email} -> {TARGET_EMAIL}: {msg}')
                    sent_ok.append(u.email)
                else:
                    print(f'FAILED -> {u.email} -> {TARGET_EMAIL}: {msg}')
                    sent_fail.append((u.email, msg))

            except Exception as exc:
                db.session.rollback()
                print(f'ERROR for {u.email}: {exc}')
                sent_fail.append((u.email, str(exc)))

        print('\nSummary:')
        print('  Successful:', len(sent_ok))
        print('  Failed:', len(sent_fail))
        if sent_fail:
            for f in sent_fail:
                print('   -', f)

if __name__ == '__main__':
    send_all()
