#!/usr/bin/env python
"""Check whether the 'addresses' table contains 'lat' and 'lng' columns."""
import sys
import pathlib
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app

def main():
    app = create_app()
    with app.app_context():
        from eacis.extensions import db
        try:
            insp = db.inspect(db.engine)
            if not insp.has_table('addresses'):
                print('addresses table: MISSING')
                return
            cols = [c['name'] for c in insp.get_columns('addresses')]
            print('addresses columns:', cols)
            print('lat present:', 'lat' in cols)
            print('lng present:', 'lng' in cols)
        except Exception as e:
            print('Error inspecting addresses table:', e)

if __name__ == '__main__':
    main()
