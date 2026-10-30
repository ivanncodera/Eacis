"""
One-off script to apply missing address columns to the DB when Alembic isn't available.
Run: .venv\Scripts\python tools\apply_address_migration.py
"""
from eacis.app import create_app
from eacis.extensions import db
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    if not insp.has_table('addresses'):
        print('addresses table not present; nothing to do')
        raise SystemExit(0)
    cols = [c['name'] for c in insp.get_columns('addresses')]
    stmts = []
    if 'house_number' not in cols:
        stmts.append("ALTER TABLE addresses ADD COLUMN house_number VARCHAR(128) NULL;")
    if 'landmark' not in cols:
        stmts.append("ALTER TABLE addresses ADD COLUMN landmark TEXT NULL;")
    if 'is_pickup' not in cols:
        stmts.append("ALTER TABLE addresses ADD COLUMN is_pickup TINYINT(1) NOT NULL DEFAULT 0;")
    if 'is_return' not in cols:
        stmts.append("ALTER TABLE addresses ADD COLUMN is_return TINYINT(1) NOT NULL DEFAULT 0;")

    if not stmts:
        print('No missing columns detected')
    else:
        print('Applying', len(stmts), 'ALTER TABLE statements')
        for s in stmts:
            print('Executing:', s)
            try:
                db.session.execute(text(s))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print('Failed:', e)
                raise
        print('Done applying columns')
