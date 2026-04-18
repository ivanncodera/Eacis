#!/usr/bin/env python3
"""
Run a minimal OTP unit test: generate an OTP in dev-preview mode and print the debug code.
"""
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path for direct script execution
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eacis.app import create_app
from eacis.config import Config
from eacis.services.otp_service import create_and_send_otp

class SmokeConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TESTING = True
    WTF_CSRF_ENABLED = False
    MAIL_ENABLED = False
    USE_DEV_SEEDS = False


def main():
    app = create_app(SmokeConfig)
    with app.app_context():
        # ensure schema exists for in-memory DB
        from eacis.extensions import db
        db.create_all()

        unique_email = 'otp-unit-test@example.com'
        challenge, msg = create_and_send_otp(unique_email, 'unit_test', user_id=None, meta={'unit': True})
        print('RESULT:', msg)
        if challenge:
            print('CHALLENGE_ID:', challenge.id)
            try:
                print('DEBUG_CODE:', challenge.meta.get('debug_code'))
            except Exception:
                print('DEBUG_CODE: <none>')

if __name__ == '__main__':
    main()
