"""
Email service for transactional notifications (OTP, security alerts, etc.).
Credentials are sourced from environment/config only.
"""
from email.message import EmailMessage
import smtplib
import ssl

from flask import current_app
import os
from datetime import datetime


class EmailService:
    @staticmethod
    def is_enabled():
        cfg = current_app.config
        return bool(cfg.get('MAIL_ENABLED') or cfg.get('MAIL_USE_FILE') or cfg.get('MAIL_USE_CONSOLE'))

    @staticmethod
    def send_email(to_email, subject, text_body, html_body=None):
        if not to_email:
            return False, 'Missing recipient email.'

        # File-backed delivery (development): write emails to a local folder
        if current_app.config.get('MAIL_USE_FILE'):
            try:
                mail_dir = current_app.config.get('MAIL_FILE_PATH') or os.path.join(current_app.instance_path, 'emails')
                if not os.path.isabs(mail_dir):
                    mail_dir = os.path.join(current_app.instance_path, mail_dir)
                os.makedirs(mail_dir, exist_ok=True)
                stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                safe_to = to_email.replace('@', '_at_').replace('/', '_')
                filename = f"{stamp}_{safe_to}.eml"
                path = os.path.join(mail_dir, filename)
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(f"To: {to_email}\nSubject: {subject}\nFrom: {current_app.config.get('MAIL_FROM_NAME')} <{current_app.config.get('MAIL_FROM_EMAIL')}>\n\n")
                    fh.write(text_body or '')
                    if html_body:
                        fh.write('\n\n--- HTML BODY ---\n')
                        fh.write(html_body)
                current_app.logger.info('Wrote email for %s to %s', to_email, path)
                return True, f'Email written to {path}'
            except Exception as exc:
                current_app.logger.exception('Failed to write email to file for %s', to_email)
                return False, f'File write failed: {exc}'

        # Console output backend
        if current_app.config.get('MAIL_USE_CONSOLE'):
            try:
                current_app.logger.info('EMAIL to %s -- Subject: %s\n%s\n%s', to_email, subject, text_body or '', html_body or '')
                # Also optionally forward to a debug address for developer inspection if configured
                forward_to = current_app.config.get('MAIL_FORWARD_TO')
                if forward_to:
                    current_app.logger.info('FORWARD (console) copy to %s for original recipient %s', forward_to, to_email)
                return True, 'Email output to console/log.'
            except Exception as exc:
                current_app.logger.exception('Failed to write email to console for %s', to_email)
                return False, f'Console output failed: {exc}'

        # SMTP backend: require host/creds
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
            # Primary delivery to the intended recipient
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
        except Exception as exc:
            current_app.logger.exception('Failed to send email to %s', to_email)
            return False, f'Email send failed: {exc}'

        # If configured, send a copy to a developer/debug inbox but do NOT treat its failure as fatal.
        forward_to = current_app.config.get('MAIL_FORWARD_TO')
        if forward_to:
            try:
                fwd = EmailMessage()
                fwd['Subject'] = f'FWD: {subject}'
                fwd['From'] = f'{from_name} <{from_email}>'
                fwd['To'] = forward_to
                fwd.set_content(f"Forwarded message for {to_email}\n\n" + (text_body or ''))
                if html_body:
                    fwd.add_alternative(html_body, subtype='html')
                if use_ssl:
                    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
                        server.login(username, password)
                        server.send_message(fwd)
                else:
                    with smtplib.SMTP(host, port) as server:
                        server.ehlo()
                        if use_tls:
                            server.starttls(context=ssl.create_default_context())
                            server.ehlo()
                        server.login(username, password)
                        server.send_message(fwd)
                current_app.logger.info('Forwarded email copy to %s for original recipient %s', forward_to, to_email)
            except Exception:
                current_app.logger.exception('Failed to forward email copy to %s (non-fatal)', forward_to)

        return True, 'Email sent.'
