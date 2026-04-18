import os
import importlib
from datetime import timedelta
from pathlib import Path

_dotenv_module = importlib.util.find_spec('dotenv')
if _dotenv_module is not None:
    load_dotenv = importlib.import_module('dotenv').load_dotenv
else:
    def load_dotenv(*args, **kwargs):
        return False

# Prefer a .env located in the package directory, fall back to default search
_pkg_dotenv = Path(__file__).resolve().parent / '.env'
if _pkg_dotenv.exists():
    load_dotenv(dotenv_path=_pkg_dotenv)
else:
    load_dotenv()

class Config:
    _raw_db_url = os.getenv("DATABASE_URL", "sqlite:///eacis_dev.db")
    # Render/Heroku style URLs may start with postgres:// which SQLAlchemy no longer accepts.
    if _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # ── Email (SMTP) ─────────────────────────────────────────────────────────
    MAIL_ENABLED = str(os.getenv('MAIL_ENABLED', 'false')).lower() in ('1', 'true', 'yes')
    MAIL_HOST = os.getenv('MAIL_HOST', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = str(os.getenv('MAIL_USE_TLS', 'true')).lower() in ('1', 'true', 'yes')
    MAIL_USE_SSL = str(os.getenv('MAIL_USE_SSL', 'false')).lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_FROM_EMAIL = os.getenv('MAIL_FROM_EMAIL', MAIL_USERNAME or 'no-reply@eacis.local')
    MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'E-ACIS Security')

    # ── OTP Security ─────────────────────────────────────────────────────────
    OTP_CODE_LENGTH = int(os.getenv('OTP_CODE_LENGTH', '6'))
    OTP_TTL_SECONDS = int(os.getenv('OTP_TTL_SECONDS', '300'))
    OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', '5'))
    OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv('OTP_RESEND_COOLDOWN_SECONDS', '60'))
    OTP_REQUESTS_PER_HOUR = int(os.getenv('OTP_REQUESTS_PER_HOUR', '8'))
    OTP_SECRET_PEPPER = os.getenv('OTP_SECRET_PEPPER', SECRET_KEY)
    # Lockout and abuse protection tuning
    OTP_FAILURES_LOCK_THRESHOLD = int(os.getenv('OTP_FAILURES_LOCK_THRESHOLD', '10'))
    OTP_FAILURES_LOCK_WINDOW_MINUTES = int(os.getenv('OTP_FAILURES_LOCK_WINDOW_MINUTES', '30'))
    OTP_LOCK_COOLDOWN_SECONDS = int(os.getenv('OTP_LOCK_COOLDOWN_SECONDS', '600'))
    OTP_DAILY_LIMIT = int(os.getenv('OTP_DAILY_LIMIT', '500'))
    LOYALTY_RATE = int(os.getenv("LOYALTY_RATE", 100))
    RETURN_WINDOW_DAYS = int(os.getenv("RETURN_WINDOW_DAYS", 7))
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # ── Return Abuse Scoring ──────────────────────────────────────────────────
    # Score >= FLAG  → account flagged for admin review
    # Score >= RESTRICT → return submissions blocked until admin clears
    # Appliances are high-value; stricter thresholds than typical marketplaces.
    RETURN_ABUSE_FLAG_THRESHOLD     = int(os.getenv("RETURN_ABUSE_FLAG_THRESHOLD", 10))
    RETURN_ABUSE_RESTRICT_THRESHOLD = int(os.getenv("RETURN_ABUSE_RESTRICT_THRESHOLD", 20))
    # Rolling window (days) for abuse score computation
    RETURN_ABUSE_WINDOW_DAYS        = int(os.getenv("RETURN_ABUSE_WINDOW_DAYS", 90))
    # Max return submissions per hour before rate-limiting
    RETURN_RATE_LIMIT_PER_HOUR      = int(os.getenv("RETURN_RATE_LIMIT_PER_HOUR", 3))

    # ── Installment Eligibility ───────────────────────────────────────────────
    # Minimum number of fully paid/delivered orders before installment is unlocked
    INSTALLMENT_MIN_COMPLETED_ORDERS = int(os.getenv("INSTALLMENT_MIN_COMPLETED_ORDERS", 1))

    # ── Evidence Upload ───────────────────────────────────────────────────────
    EVIDENCE_UPLOAD_SUBDIR = os.getenv("EVIDENCE_UPLOAD_SUBDIR", "evidence")
    # Control CSRF token lifetime (seconds). Set to 'None' to disable expiration for development.
    _raw_csrf_tl = os.getenv('WTF_CSRF_TIME_LIMIT', None)
    if _raw_csrf_tl is None:
        WTF_CSRF_TIME_LIMIT = 3600
    else:
        try:
            if str(_raw_csrf_tl).lower() == 'none':
                WTF_CSRF_TIME_LIMIT = None
            else:
                WTF_CSRF_TIME_LIMIT = int(_raw_csrf_tl)
        except Exception:
            WTF_CSRF_TIME_LIMIT = 3600
    # Control whether to run development seeds on app startup.
    # If USE_DEV_SEEDS is not set, enable it automatically in development mode.
    _raw_use_dev = os.getenv('USE_DEV_SEEDS')
    if _raw_use_dev is None:
        _env = os.getenv('FLASK_ENV', '').lower()
        USE_DEV_SEEDS = _env == 'development'
    else:
        USE_DEV_SEEDS = str(_raw_use_dev).lower() in ('1', 'true', 'yes')

    # Security defaults for production deployments.
    _is_prod = os.getenv('FLASK_ENV', '').lower() == 'production'
    SESSION_COOKIE_SECURE = _is_prod
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict' if _is_prod else 'Lax'
    REMEMBER_COOKIE_SECURE = _is_prod
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Strict' if _is_prod else 'Lax'
    PREFERRED_URL_SCHEME = 'https' if _is_prod else 'http'
    WTF_CSRF_ENABLED = True
