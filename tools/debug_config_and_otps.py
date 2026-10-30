import os, pathlib, sys
sys.path.insert(0,str(pathlib.Path('.').resolve()))
from eacis.app import create_app
from eacis.models.otp_challenge import OtpChallenge
app = create_app()
print('ENV FLASK_ENV:', os.getenv('FLASK_ENV'))
with app.app_context():
    print('app.config DEV_SHOW_OTP_IN_UI:', app.config.get('DEV_SHOW_OTP_IN_UI'))
    print('app.config MAIL_ENABLED:', app.config.get('MAIL_ENABLED'))
    rows = OtpChallenge.query.order_by(OtpChallenge.created_at.desc()).limit(5).all()
    print('Recent OTPs count:', len(rows))
    for r in rows:
        print('id', r.id, 'email', r.email, 'meta_debug', (r.meta or {}).get('debug_code'))
