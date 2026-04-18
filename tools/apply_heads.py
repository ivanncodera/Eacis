#!/usr/bin/env python3
"""Apply all unapplied Alembic migrations (upgrade to heads)."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eacis.app import create_app
from flask_migrate import upgrade


def main():
    app = create_app()
    with app.app_context():
        print('Upgrading DB to heads...')
        upgrade(revision='heads')
        print('Upgrade to heads complete.')


if __name__ == '__main__':
    main()
