"""
Email service for transactional notifications (OTP, security alerts, etc.).
Credentials are sourced from environment/config only.
"""
from email.message import EmailMessage
import smtplib
import ssl

from flask import current_app


class EmailService:
    @staticmethod
    def is_enabled():
        return bool(current_app.config.get('MAIL_ENABLED'))

    @staticmethod
    def send_email(to_email, subject, text_body, html_body=None):
        if not to_email:
            return False, 'Missing recipient email.'

        if not EmailService.is_enabled():
            current_app.logger.info('MAIL_ENABLED is false; skipped email send to %s', to_email)
            return False, 'Email sending is disabled.'

        host = current_app.config.get('MAIL_HOST')
        port = int(current_app.config.get('MAIL_PORT') or 587)
        username = current_app.config.get('MAIL_USERNAME')
        password = current_app.config.get('MAIL_PASSWORD')
        use_tls = bool(current_app.config.get('MAIL_USE_TLS'))
        use_ssl = bool(current_app.config.get('MAIL_USE_SSL'))
        from_email = current_app.config.get('MAIL_FROM_EMAIL') or username
        from_name = current_app.config.get('MAIL_FROM_NAME') or 'E-ACIS Security'

        if not host or not username or not password or not from_email:
            return False, 'Email configuration is incomplete.'

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = f'{from_name} <{from_email}>'
        msg['To'] = to_email
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype='html')

        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
                    server.login(username, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port) as server:
                    server.ehlo()
                    if use_tls:
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                    server.login(username, password)
                    server.send_message(msg)
            return True, 'Email sent.'
        except Exception as exc:
            current_app.logger.exception('Failed to send email to %s', to_email)
            return False, f'Email send failed: {exc}'
