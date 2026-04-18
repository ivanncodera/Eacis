#!/usr/bin/env python3
"""Quick smoke test: call get_reviews for product id 1 to ensure ORM reads work."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eacis.app import create_app


def main():
    app = create_app()
    with app.app_context():
        try:
            from eacis.services.review_service import get_reviews
        except Exception:
            from services.review_service import get_reviews
        try:
            reviews = get_reviews(1, limit=3, offset=0)
            print('Fetched', len(reviews), 'reviews. Sample:', [(r.id, getattr(r, 'rating', None)) for r in reviews])
        except Exception as e:
            print('Error fetching reviews:', e)


if __name__ == '__main__':
    main()
