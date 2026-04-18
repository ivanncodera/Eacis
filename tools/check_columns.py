from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from pathlib import Path
pkg_dotenv = Path(__file__).resolve().parent.parent / 'eacis' / '.env'
if pkg_dotenv.exists():
    load_dotenv(dotenv_path=pkg_dotenv)
DB = os.getenv('DATABASE_URL') or 'mysql+pymysql://root:YourNewPassword@localhost:3307/eacis'
engine = create_engine(DB)
with engine.connect() as conn:
    for tbl, col in [('users','email_verified_at'), ('vouchers','target_category')]:
        try:
            r = conn.execute(text(f"SHOW COLUMNS FROM {tbl} LIKE '{col}'"))
            exists = bool(list(r))
            print(f"{tbl}.{col} exists: {exists}")
        except Exception as e:
            print(f"Error checking {tbl}.{col}: {e}")
