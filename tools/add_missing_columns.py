"""Add specific missing columns to the MySQL database used by this project.

Currently used to add `users.email_verified_at` when it's absent.
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from pathlib import Path
pkg_dotenv = Path(__file__).resolve().parent.parent / 'eacis' / '.env'
if pkg_dotenv.exists():
    load_dotenv(dotenv_path=pkg_dotenv)
DB = os.getenv('DATABASE_URL') or 'mysql+pymysql://root:YourNewPassword@localhost:3307/eacis'
engine = create_engine(DB)
with engine.begin() as conn:
    # check users.email_verified_at
    try:
        r = conn.execute(text("SHOW COLUMNS FROM users LIKE 'email_verified_at'"))
        if not list(r):
            print('Adding users.email_verified_at...')
            conn.execute(text('ALTER TABLE users ADD COLUMN email_verified_at DATETIME NULL'))
            print('Added users.email_verified_at')
        else:
            print('users.email_verified_at already present')
    except Exception as e:
        print('Error while checking/adding users.email_verified_at:', e)
        raise
