from eacis.app import create_app
from eacis.extensions import db
from eacis.models.product import Product
from eacis.models.review import Review
from eacis.models.product_star import ProductStar
from eacis.models.user import User


def test_seeded_reviews_exist():
    app = create_app()
    with app.app_context():
        # At least one approved review should exist
        total_reviews = Review.query.filter(Review.is_approved == True).count()
        assert total_reviews >= 2
        p = Product.query.filter_by(product_ref='REF-001').first()
        assert p is not None
        assert Review.query.filter_by(product_id=p.id, rating=5).count() >= 1


def test_reviewers_and_stars():
    app = create_app()
    with app.app_context():
        customer = User.query.filter_by(email='customer@demo.com').first()
        assert customer is not None
        p = Product.query.filter_by(product_ref='REF-001').first()
        assert p is not None
        # customer left a 5-star review and starred the product
        assert Review.query.filter_by(product_id=p.id, user_id=customer.id, rating=5).count() >= 1
        assert ProductStar.query.filter_by(product_id=p.id, user_id=customer.id).count() >= 1
