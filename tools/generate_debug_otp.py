import sys, pathlib
# Ensure project root is on sys.path when running this script directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from eacis.app import create_app
from eacis.services.otp_service import create_and_send_otp
from flask import current_app

app = create_app()
with app.app_context():
    # Force dev UI debug code on for this run
    current_app.config['DEV_SHOW_OTP_IN_UI'] = True
    # Choose an account that exists in seeds (customer@demo.com)
    email = 'customer@demo.com'
    challenge, msg = create_and_send_otp(email, purpose='login', user_id=None, ip_address='127.0.0.1', user_agent='tools/generate_debug_otp')
    if not challenge:
        print('Failed to create OTP:', msg)
    else:
        debug_code = (challenge.meta or {}).get('debug_code')
        print('Created challenge id:', getattr(challenge, 'id', None))
        print('Debug code:', debug_code)
        print('Message:', msg)
