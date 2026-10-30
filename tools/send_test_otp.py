from eacis.app import create_app
from eacis.extensions import db
from eacis.models.user import User
from eacis.services.otp_service import create_and_send_otp

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='customer@demo.com').first()
    if not user:
        print('No user with email customer@demo.com')
    else:
        challenge, msg = create_and_send_otp(user.email, 'register_verify', user_id=user.id, ip_address='127.0.0.1', user_agent='test-agent')
        print('create_and_send_otp ->', bool(challenge), msg)
        if challenge and challenge.meta:
            print('challenge.meta:', challenge.meta)
