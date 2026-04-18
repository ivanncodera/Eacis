"""Small helper to widen alembic_version.version_num to accommodate long revision names.

Usage: python tools/fix_alembic_version.py

It reads DATABASE_URL from eacis/.env if python-dotenv is available, otherwise falls back to
an explicit URL configured at the top of this file. Change `FALLBACK_URL` if needed.
"""
from sqlalchemy import create_engine, text
import os

FALLBACK_URL = os.getenv('DATABASE_URL') or 'mysql+pymysql://root:YourNewPassword@localhost:3307/eacis'

try:
    # try to load package .env
    from dotenv import load_dotenv
    from pathlib import Path
    pkg_dotenv = Path(__file__).resolve().parent.parent / 'eacis' / '.env'
    if pkg_dotenv.exists():
        load_dotenv(dotenv_path=pkg_dotenv)
except Exception:
    pass

db_url = os.getenv('DATABASE_URL') or FALLBACK_URL
print('Using DB URL:', db_url)
engine = create_engine(db_url)

with engine.begin() as conn:
    # alter column to varchar(255) if necessary
    try:
        conn.execute(text("ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(255)"))
        print('Column altered to VARCHAR(255).')
    except Exception as exc:
        print('Failed to alter column:', exc)
        raise
