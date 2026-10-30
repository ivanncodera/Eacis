#!/usr/bin/env python
"""Stamp a specific alembic revision as applied using Flask-Migrate."""
import sys
import pathlib

project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app

def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/stamp_revision.py <revision>')
        sys.exit(2)
    rev = sys.argv[1]
    app = create_app()
    with app.app_context():
        try:
            from flask_migrate import stamp
            stamp(revision=rev)
            print('Stamped revision', rev)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()
