#!/usr/bin/env python3
"""
Send a quick test email using app config.

Usage: python tools/send_test_email.py --to you@example.com
Requires MAIL_ENABLED and MAIL_USERNAME & MAIL_PASSWORD set in env or .env.
"""
import argparse
from eacis.app import create_app
from eacis.services.email_service import EmailService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--subject", default="E-ACIS test email", help="Subject")
    parser.add_argument("--body", default="This is a test email from E-ACIS.", help="Text body")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        ok, msg = EmailService.send_email(args.to, args.subject, args.body)
        print("OK:", ok)
        print("MSG:", msg)


if __name__ == "__main__":
    main()
