from eacis.app import create_app
from eacis.extensions import db
from eacis.models.otp_challenge import OtpChallenge
from flask import current_app

app = create_app()
with app.app_context():
    print('MAIL_ENABLED:', current_app.config.get('MAIL_ENABLED'))
    print('MAIL_USE_CONSOLE:', current_app.config.get('MAIL_USE_CONSOLE'))
    print('MAIL_USE_FILE:', current_app.config.get('MAIL_USE_FILE'))
    print('MAIL_HOST:', current_app.config.get('MAIL_HOST'))
    print('MAIL_USERNAME:', current_app.config.get('MAIL_USERNAME'))
    print('\nRecent OTP challenges:')
    rows = OtpChallenge.query.order_by(OtpChallenge.created_at.desc()).limit(20).all()
    print('Count:', len(rows))
    for o in rows:
        print('---')
        print('id:', o.id)
        print('for_email:', o.email)
        print('sent_to:', o.sent_to)
        print('purpose:', o.purpose)
        print('meta:', o.meta)
        print('created_at:', o.created_at)
        print('expires_at:', o.expires_at)
        print('consumed_at:', o.consumed_at)
        print('failure_reason:', o.failure_reason)
