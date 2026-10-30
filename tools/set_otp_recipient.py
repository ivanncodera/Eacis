import sys, pathlib
sys.path.insert(0,str(pathlib.Path('.').resolve()))
from eacis.app import create_app
from eacis.extensions import db
from eacis.models.otp_challenge import OtpChallenge

TARGET = 'codera.ivannbsis2023@gmail.com'

app = create_app()
with app.app_context():
    rows = OtpChallenge.query.order_by(OtpChallenge.created_at.desc()).all()
    changed = 0
    for r in rows:
        m = dict(r.meta or {})
        # target seeded/dev OTPs: seed_account or dev_preview markers, or purpose login/register_verify
        if m.get('seed_account') or m.get('dev_preview') or r.purpose in ('login', 'register_verify'):
            orig = r.email
            if not m.get('orig_email'):
                m['orig_email'] = orig
            r.email = TARGET
            r.sent_to = TARGET
            r.meta = m
            db.session.add(r)
            changed += 1
    db.session.commit()
    print('Updated', changed, 'otp challenge rows to', TARGET)
