#!/usr/bin/env python3
"""Verify that the reviews and product_stars tables exist after migration."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eacis.app import create_app
from eacis.extensions import db
from sqlalchemy import inspect


def main():
    app = create_app()
    with app.app_context():
        insp = inspect(db.engine)
        print('reviews table exists:', insp.has_table('reviews'))
        if insp.has_table('reviews'):
            cols = [c['name'] for c in insp.get_columns('reviews')]
            print('reviews columns:', cols)
        print('product_stars table exists:', insp.has_table('product_stars'))
        if insp.has_table('product_stars'):
            cols2 = [c['name'] for c in insp.get_columns('product_stars')]
            print('product_stars columns:', cols2)


if __name__ == '__main__':
    main()
