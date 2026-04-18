"""
OTP service primitives for challenge creation and verification.
"""
from datetime import datetime, timedelta
import hashlib
import secrets

from flask import current_app, url_for

# Import db and models with fallbacks to support package vs module execution
try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db

try:
    from eacis.models.otp_challenge import OtpChallenge
except Exception:
    try:
        from ..models.otp_challenge import OtpChallenge
    except Exception:
        from models.otp_challenge import OtpChallenge

try:
    from eacis.models.audit import AuditLog
except Exception:
    try:
        from ..models.audit import AuditLog
    except Exception:
        from models.audit import AuditLog

try:
    from eacis.services.email_service import EmailService
except Exception:
    try:
        from .email_service import EmailService
    except Exception:
        from services.email_service import EmailService


def _hash_code(code):
    pepper = str(current_app.config.get('OTP_SECRET_PEPPER') or '')
    raw = f'{pepper}:{code}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _generate_code(length):
    # Numeric OTP code generator
    return ''.join(str(secrets.randbelow(10)) for _ in range(length))


def can_issue_otp(email, purpose, ip_address=None):
    """Determine whether an OTP may be issued for a given email/purpose.

    Returns (allowed: bool, message: str)
    """
    now = datetime.utcnow()
    cooldown = int(current_app.config.get('OTP_RESEND_COOLDOWN_SECONDS') or 60)
    per_hour_limit = int(current_app.config.get('OTP_REQUESTS_PER_HOUR') or 8)

    latest = (
        OtpChallenge.query
        .filter_by(email=email, purpose=purpose)
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    if latest and (now - latest.created_at).total_seconds() < cooldown:
        wait_for = cooldown - int((now - latest.created_at).total_seconds())
        return False, f'Resend cooldown active. Try again in {wait_for}s.'

    hour_start = now - timedelta(hours=1)
    q = OtpChallenge.query.filter(
        OtpChallenge.email == email,
        OtpChallenge.purpose == purpose,
        OtpChallenge.created_at >= hour_start,
    )
    if ip_address:
        q = q.filter(OtpChallenge.ip_address == ip_address)
    if q.count() >= per_hour_limit:
        return False, 'Too many OTP requests. Please try later.'

    # Additional abuse protection: recent invalid attempts lockout and daily caps
    try:
        window_min = int(current_app.config.get('OTP_FAILURES_LOCK_WINDOW_MINUTES') or 30)
        lock_threshold = int(current_app.config.get('OTP_FAILURES_LOCK_THRESHOLD') or 10)
        window_start = now - timedelta(minutes=window_min)
        recent_failures = OtpChallenge.query.filter(
            OtpChallenge.email == email,
            OtpChallenge.created_at >= window_start,
            OtpChallenge.failure_reason.in_(['invalid_code', 'max_attempts', 'locked'])
        ).count()
        if ip_address:
            recent_ip_failures = OtpChallenge.query.filter(
                OtpChallenge.ip_address == ip_address,
                OtpChallenge.created_at >= window_start,
                OtpChallenge.failure_reason.in_(['invalid_code', 'max_attempts', 'locked'])
            ).count()
        else:
            recent_ip_failures = 0
        if recent_failures >= lock_threshold or recent_ip_failures >= lock_threshold:
            try:
                al = AuditLog(action='otp_rate_limited', module='otp', target_ref=email, meta={'recent_failures': recent_failures, 'recent_ip_failures': recent_ip_failures})
                db.session.add(al)
                db.session.commit()
            except Exception:
                current_app.logger.exception('Failed to write OTP rate-limit audit')
            return False, 'Too many recent failed OTP attempts. Try again later.'

        daily_limit = int(current_app.config.get('OTP_DAILY_LIMIT') or 500)
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = OtpChallenge.query.filter(OtpChallenge.email == email, OtpChallenge.created_at >= start_today).count()
        if daily_count >= daily_limit:
            try:
                al = AuditLog(action='otp_rate_limited', module='otp', target_ref=email, meta={'daily_count': daily_count})
                db.session.add(al)
                db.session.commit()
            except Exception:
                current_app.logger.exception('Failed to write OTP daily-limit audit')
            return False, 'Daily OTP limit reached. Try again tomorrow.'
    except Exception:
        # Do not block issuance if analytics checks fail; log and continue
        current_app.logger.exception('OTP abuse-protection check failed')

    return True, 'ok'


def create_and_send_otp(email, purpose, user_id=None, ip_address=None, user_agent=None, meta=None):
    allowed, message = can_issue_otp(email, purpose, ip_address=ip_address)
    if not allowed:
        return None, message

    try:
        al = AuditLog(action='otp_requested', module='otp', target_ref=email, meta={'purpose': purpose, 'user_id': user_id})
        db.session.add(al)
        db.session.commit()
    except Exception:
        current_app.logger.exception('Failed to write OTP requested audit')

    length = int(current_app.config.get('OTP_CODE_LENGTH') or 6)
    ttl_seconds = int(current_app.config.get('OTP_TTL_SECONDS') or 300)
    max_attempts = int(current_app.config.get('OTP_MAX_ATTEMPTS') or 5)

    # Invalidate older active challenges for the same email/purpose.
    active_challenges = (
        OtpChallenge.query
        .filter(
            OtpChallenge.email == email,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
        )
        .all()
    )
    for old_challenge in active_challenges:
        old_challenge.consumed_at = datetime.utcnow()
        old_challenge.failure_reason = 'superseded'

    code = _generate_code(length)
    activation_token = secrets.token_urlsafe(24)
    challenge = OtpChallenge(
        user_id=user_id,
        email=email,
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
        max_attempts=max_attempts,
        ip_address=ip_address,
        user_agent=(user_agent or '')[:255] if user_agent else None,
        sent_to=email,
        meta=dict(meta or {}, activation_token=activation_token),
    )
    db.session.add(challenge)
    db.session.flush()

    try:
        al = AuditLog(action='otp_created', module='otp', target_ref=email, meta={'challenge_id': None, 'purpose': purpose, 'dev_preview': not EmailService.is_enabled()})
        try:
            al.meta['challenge_id'] = challenge.id
        except Exception:
            pass
        db.session.add(al)
        db.session.commit()
    except Exception:
        current_app.logger.exception('Failed to write OTP created audit')

    is_production = str(current_app.config.get('FLASK_ENV') or '').lower() == 'production'
    if not EmailService.is_enabled():
        if is_production:
            db.session.rollback()
            return None, 'Email delivery is disabled.'
        challenge.meta = dict(challenge.meta or {})
        challenge.meta['debug_code'] = code
        challenge.meta['dev_preview'] = True
        try:
            al = AuditLog(action='otp_generated_dev', module='otp', target_ref=email, meta={'challenge_id': challenge.id, 'debug_code': code, 'purpose': purpose})
            db.session.add(al)
        except Exception:
            current_app.logger.exception('Failed to write OTP dev audit')
        db.session.commit()
        current_app.logger.info('DEV OTP for %s (%s): %s', email, purpose, code)
        return challenge, 'OTP generated in development mode.'

    subject = f'E-ACIS Security Code ({purpose.replace("_", " ").title()})'
    text_body = (
        f'Your E-ACIS verification code is: {code}\n\n'
        f'This code expires in {ttl_seconds // 60} minutes.\n'
        'If you did not request this, you can ignore this email.'
    )
    html_body = (
        '<div style="font-family:Arial,sans-serif;line-height:1.6">'
        '<h2>E-ACIS Security Verification</h2>'
        f'<p>Purpose: <strong>{purpose.replace("_", " ").title()}</strong></p>'
        f'<p>Your one-time code is:</p><p style="font-size:28px;font-weight:700;letter-spacing:3px">{code}</p>'
        f'<p>This code expires in <strong>{ttl_seconds // 60} minutes</strong>.</p>'
        '<p>If you did not request this code, please ignore this message and secure your account.</p>'
        '</div>'
    )

    if str(purpose or '').strip() == 'register_verify':
        try:
            token = challenge.meta.get('activation_token') if challenge.meta else None
            if token:
                verify_url = url_for('auth_register_verify', token=token, _external=True)
                text_body = text_body + f"\n\nOr click the following link to verify your email and activate your account:\n{verify_url}"
                html_body = html_body + f"<p><a href=\"{verify_url}\" style=\"display:inline-block;padding:10px 16px;background:#0b5cff;color:#fff;border-radius:6px;text-decoration:none;\">Verify your email</a></p>"
        except Exception:
            current_app.logger.exception('Failed to build register verify URL for OTP email')

    sent, send_msg = EmailService.send_email(email, subject, text_body, html_body=html_body)
    if not sent:
        try:
            al = AuditLog(action='otp_send_failed', module='otp', target_ref=email, meta={'error': send_msg, 'purpose': purpose})
            db.session.add(al)
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to write OTP send-failed audit')
        return None, send_msg

    try:
        al = AuditLog(action='otp_sent', module='otp', target_ref=email, meta={'challenge_id': challenge.id, 'purpose': purpose})
        db.session.add(al)
    except Exception:
        current_app.logger.exception('Failed to write OTP sent audit')
    db.session.commit()
    return challenge, 'OTP sent.'


def verify_activation_token(token):
    """Verify a one-time activation token created for registration flows.

    Returns (ok: bool, message: str, challenge: OtpChallenge|None)
    """
    if not token:
        try:
            al = AuditLog(action='otp_verify_missing', module='otp', target_ref=str(token))
            db.session.add(al)
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to write OTP verify-missing audit')
        return False, 'Invalid verification link.', None

    try:
        candidates = OtpChallenge.query.filter_by(purpose='register_verify').order_by(OtpChallenge.created_at.desc()).all()
    except Exception:
        current_app.logger.exception('Error while querying activation challenges')
        return False, 'Invalid verification link.', None

    for chal in candidates:
        try:
            if not chal.meta:
                continue
            if chal.meta.get('activation_token') != token:
                continue

            if chal.is_consumed:
                try:
                    al = AuditLog(action='otp_already_used', module='otp', target_ref=chal.email, meta={'challenge_id': chal.id})
                    db.session.add(al)
                    db.session.commit()
                except Exception:
                    current_app.logger.exception('Failed to write OTP already-used audit')
                return False, 'This verification link has already been used.', None

            if chal.is_expired:
                try:
                    chal.consumed_at = datetime.utcnow()
                    chal.failure_reason = 'expired'
                    db.session.add(chal)
                    al = AuditLog(action='otp_expired', module='otp', target_ref=chal.email, meta={'challenge_id': chal.id})
                    db.session.add(al)
                    db.session.commit()
                except Exception:
                    current_app.logger.exception('Failed to mark expired challenge')
                return False, 'Verification link has expired.', None

            # mark as verified
            chal.verified_at = datetime.utcnow()
            chal.consumed_at = datetime.utcnow()
            chal.failure_reason = None
            db.session.add(chal)
            try:
                al = AuditLog(action='otp_verified', module='otp', target_ref=chal.email, meta={'challenge_id': chal.id})
                db.session.add(al)
                db.session.commit()
            except Exception:
                current_app.logger.exception('Failed to write OTP verified audit')
            return True, 'Verified', chal
        except Exception:
            current_app.logger.exception('Error processing activation candidate')
            continue

    try:
        al = AuditLog(action='otp_verify_missing', module='otp', target_ref=str(token))
        db.session.add(al)
        db.session.commit()
    except Exception:
        current_app.logger.exception('Failed to write OTP verify-missing audit')
    return False, 'Invalid verification link.', None


def verify_otp(challenge_id, code_input):
    challenge = OtpChallenge.query.get(challenge_id)
    if not challenge:
        try:
            al = AuditLog(action='otp_verify_missing', module='otp', target_ref=str(challenge_id))
            db.session.add(al)
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to write OTP verify-missing audit')
        return False, 'Challenge not found.'

    if challenge.is_consumed:
        try:
            al = AuditLog(action='otp_already_used', module='otp', target_ref=challenge.email, meta={'challenge_id': challenge.id})
            db.session.add(al)
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to write OTP already-used audit')
        return False, 'This OTP has already been used.'

    if challenge.is_expired:
        try:
            challenge.failure_reason = 'expired'
            if not challenge.consumed_at:
                challenge.consumed_at = datetime.utcnow()
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to mark expired challenge')
        try:
            al = AuditLog(action='otp_expired', module='otp', target_ref=challenge.email, meta={'challenge_id': challenge.id})
            db.session.add(al)
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to write OTP expired audit')
        return False, 'OTP expired. Request a new code.'

    if int(challenge.attempt_count or 0) >= int(challenge.max_attempts or 5):
        try:
            challenge.failure_reason = 'max_attempts'
            if not challenge.consumed_at:
                challenge.consumed_at = datetime.utcnow()
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to mark max-attempts challenge')
        try:
            al = AuditLog(action='otp_locked', module='otp', target_ref=challenge.email, meta={'challenge_id': challenge.id})
            db.session.add(al)
            db.session.commit()
        except Exception:
            current_app.logger.exception('Failed to write OTP locked audit')
        return False, 'Maximum attempts reached. Request a new code.'

    # consume an attempt
    challenge.attempt_count = int(challenge.attempt_count or 0) + 1
    provided_hash = _hash_code(str(code_input or '').strip())
    if provided_hash != challenge.code_hash:
        try:
            if challenge.attempt_count >= int(challenge.max_attempts or 5):
                challenge.failure_reason = 'max_attempts'
                challenge.consumed_at = datetime.utcnow()
                db.session.commit()
                try:
                    al = AuditLog(action='otp_locked', module='otp', target_ref=challenge.email, meta={'challenge_id': challenge.id, 'attempt_count': challenge.attempt_count})
                    db.session.add(al)
                    db.session.commit()
                except Exception:
                    current_app.logger.exception('Failed to write OTP locked audit')
                return False, 'Maximum attempts reached. Request a new code.'
            else:
                challenge.failure_reason = 'invalid_code'
                db.session.commit()
                try:
                    al = AuditLog(action='otp_invalid', module='otp', target_ref=challenge.email, meta={'challenge_id': challenge.id, 'attempt_count': challenge.attempt_count})
                    db.session.add(al)
                    db.session.commit()
                except Exception:
                    current_app.logger.exception('Failed to write OTP invalid audit')
                return False, 'Invalid OTP code.'
        except Exception:
            current_app.logger.exception('Error processing OTP invalidation')
            return False, 'Invalid OTP code.'

    # success
    challenge.verified_at = datetime.utcnow()
    challenge.consumed_at = datetime.utcnow()
    challenge.failure_reason = None
    try:
        db.session.commit()
    except Exception:
        current_app.logger.exception('Failed to commit OTP verification')
    try:
        al = AuditLog(action='otp_verified', module='otp', target_ref=challenge.email, meta={'challenge_id': challenge.id})
        db.session.add(al)
        db.session.commit()
    except Exception:
        current_app.logger.exception('Failed to write OTP verified audit')
    return True, 'OTP verified.'
