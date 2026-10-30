#!/usr/bin/env python
"""Check alembic migration status (alembic_version table contents)."""
import sys
import pathlib
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app
from sqlalchemy import text

def main():
    app = create_app()
    with app.app_context():
        from eacis.extensions import db
        try:
            res = db.session.execute(text('SELECT * FROM alembic_version')).fetchall()
            if not res:
                print('alembic_version: <empty>')
            else:
                for row in res:
                    try:
                        print('alembic_version row:', dict(row._mapping))
                    except Exception:
                        print('alembic_version row raw:', row)
        except Exception as e:
            print('Could not read alembic_version table:', e)

if __name__ == '__main__':
    main()
