#!/usr/bin/env python3
"""Run Flask-Migrate/Alembic upgrades programmatically."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eacis.app import create_app
from flask_migrate import upgrade


def main():
    app = create_app()
    with app.app_context():
        print('Stamping DB to baseline revision before applying new migration...')
        from flask_migrate import stamp
        try:
            # mark existing migrations as applied up to the last known migration
            stamp(revision='20260416_add_return_updated_at')
            print('DB stamped to 20260416_add_return_updated_at')
        except Exception as ex:
            print('Stamp failed or already stamped:', ex)

        print('Applying new migration 20260417_add_reviews_and_product_stars...')
        upgrade(revision='20260417_add_reviews_and_product_stars')
        print('Migrations applied.')


if __name__ == '__main__':
    main()
