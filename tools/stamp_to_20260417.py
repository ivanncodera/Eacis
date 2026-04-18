#!/usr/bin/env python3
"""Stamp the DB migration head to 20260417_add_reviews_and_product_stars without applying DDL.

Use when the schema already contains the necessary tables created outside Alembic.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eacis.app import create_app
from flask_migrate import stamp


def main():
    app = create_app()
    with app.app_context():
        print('Stamping DB to 20260417_add_reviews_and_product_stars')
        stamp(revision='20260417_add_reviews_and_product_stars')
        print('Stamped.')


if __name__ == '__main__':
    main()
