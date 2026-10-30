"""Quick verification script for /shop filters using Flask test client.

Usage: python tools/run_shop_filter_check.py

This script:
- boots the app with create_app()
- prints available categories
- GET /shop and prints a short HTML excerpt
- selects the first category and GET /shop?category=<name> and reports product counts
"""
import sys
import os
from pprint import pprint

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.product import Product


def main():
    app = create_app()
    with app.app_context():
        print('DB engine:', getattr(db, 'engine', None))
        cats = [r[0] for r in db.session.query(Product.category).distinct().order_by(Product.category.asc()).all() if r[0]]
        print('\nFound categories (count={}):'.format(len(cats)))
        for i, c in enumerate(cats[:20], start=1):
            print(f'{i}.', c)

        client = app.test_client()
        resp = client.get('/shop')
        print('\nGET /shop ->', resp.status_code)
        body = resp.get_data(as_text=True)
        print('Response excerpt:')
        print(body[:2000])

        if cats:
            first = cats[0]
            print(f"\nTesting category filter for: {first}")
            resp2 = client.get('/shop', query_string={'category': first})
            print('/shop?category= ->', resp2.status_code)
            b2 = resp2.get_data(as_text=True)
            # crude count: number of product cards on page (search for product-card marker)
            cnt = b2.count('product-card')
            print('Approx product-card count in response:', cnt)
            # attempt to locate the __products__ JSON embedded in the page
            marker = '<script id="__products__"'
            i = b2.find(marker)
            if i != -1:
                start = b2.find('>', i) + 1
                end = b2.find('</script>', start)
                snippet = b2[start:end].strip()[:2000]
                print('\n__products__ JSON excerpt:')
                print(snippet)
            else:
                print('\nNo __products__ script found in category response')
        else:
            print('No categories found; run tools/add_categories.py first to seed demo categories.')


if __name__ == '__main__':
    main()
