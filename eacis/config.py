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
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///eacis_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    LOYALTY_RATE = int(os.getenv("LOYALTY_RATE", 100))
    RETURN_WINDOW_DAYS = int(os.getenv("RETURN_WINDOW_DAYS", 7))
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
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
