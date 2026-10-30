from eacis.app import create_app
from eacis.extensions import db
from eacis.models.otp_challenge import OtpChallenge
from eacis.models.user import User
import re

app = create_app()

with app.app_context():
    with app.test_client() as client:
        # Case: session has otp_challenge_id pointing to an existing challenge
        chal = OtpChallenge.query.order_by(OtpChallenge.id.desc()).first()
        if not chal:
            print('No OTP challenges in DB; aborting test')
        else:
            with client.session_transaction() as sess:
                sess['otp_challenge_id'] = chal.id

        resp = client.get('/auth/verify-required')
        print('Status:', resp.status_code)
        body = resp.get_data(as_text=True)
        m = re.search(r"To activate your account we sent a verification message to <strong>([^<]+)</strong>", body)
        if m:
            print('Displayed email:', m.group(1))
        else:
            print('Could not find email in rendered template')

        # Case: session has otp_user_id -> should show canonical user email
        user = User.query.order_by(User.id).first()
        if user:
            with client.session_transaction() as sess:
                sess.clear()
                sess['otp_user_id'] = user.id
            resp2 = client.get('/auth/verify-required')
            body2 = resp2.get_data(as_text=True)
            m2 = re.search(r"To activate your account we sent a verification message to <strong>([^<]+)</strong>", body2)
            print('User id:', user.id, 'expected email:', user.email)
            if m2:
                print('Displayed email for user_id:', m2.group(1))
            else:
                print('Could not find email in second render')
        else:
            print('No users found for user_id test')
from eacis.app import create_app
from eacis.extensions import db
from eacis.models.otp_challenge import OtpChallenge
from eacis.models.user import User

app = create_app()
with app.app_context():
    with app.test_client() as client:
        # Case: session has otp_challenge_id pointing to an existing challenge
        chal = OtpChallenge.query.order_by(OtpChallenge.id.desc()).first()
        if not chal:
            print('No OTP challenges in DB; aborting test')
        else:
            with client.session_transaction() as sess:
                sess['otp_challenge_id'] = chal.id
        resp = client.get('/auth/verify-required')
            print('Status:', resp.status_code)
            body = resp.get_data(as_text=True)
    # print a short excerpt around the verify sentence
    import re
    m = re.search(r"To activate your account we sent a verification message to <strong>([^<]+)</strong>", body)
    if m:
        print('Displayed email:', m.group(1))
    else:
        print('Could not find email in rendered template')

        # Case: session has otp_user_id -> should show canonical user email
        user = User.query.order_by(User.id).first()
        if user:
            with client.session_transaction() as sess:
                sess.clear()
                sess['otp_user_id'] = user.id
            resp2 = client.get('/auth/verify-required')
            body2 = resp2.get_data(as_text=True)
            m2 = re.search(r"To activate your account we sent a verification message to <strong>([^<]+)</strong>", body2)
            print('User id:', user.id, 'expected email:', user.email)
            if m2:
                print('Displayed email for user_id:', m2.group(1))
            else:
                print('Could not find email in second render')
        else:
            print('No users found for user_id test')
