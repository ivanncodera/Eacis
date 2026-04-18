from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from pathlib import Path
pkg_dotenv = Path(__file__).resolve().parent.parent / 'eacis' / '.env'
if pkg_dotenv.exists():
    load_dotenv(dotenv_path=pkg_dotenv)

DB = os.getenv('DATABASE_URL') or 'mysql+pymysql://root:YourNewPassword@localhost:3307/eacis'
print('Using DB:', DB)
engine = create_engine(DB)
with engine.connect() as conn:
    try:
        r = conn.execute(text('SELECT version_num FROM alembic_version'))
        rows = [row[0] for row in r]
        print('alembic_version rows:', rows)
    except Exception as e:
        print('Could not read alembic_version:', e)
    try:
        r = conn.execute(text("SHOW COLUMNS FROM vouchers LIKE 'target_category'"))
        print('vouchers.target_category column:', list(r))
    except Exception as e:
        print('Error checking vouchers table:', e)
