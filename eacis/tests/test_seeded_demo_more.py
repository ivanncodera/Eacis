from eacis.app import create_app
from eacis.extensions import db
from eacis.models.review import Review
from eacis.models.user import User
from eacis.models.return_request import ReturnRequest
from eacis.models.refund_transaction import RefundTransaction
from eacis.models.product import Product
from eacis.models.order import Order


def test_flagged_review_and_ticket():
    app = create_app()
    with app.app_context():
        reviewer3 = User.query.filter_by(email='reviewer3@demo.com').first()
        assert reviewer3 is not None
        flagged = Review.query.filter_by(user_id=reviewer3.id, is_approved=False).first()
        assert flagged is not None


def test_disputed_refund_exists():
    app = create_app()
    with app.app_context():
        rrt = ReturnRequest.query.filter_by(rrt_ref='RRT-2002').first()
        assert rrt is not None and rrt.status == 'rejected'
        rf = RefundTransaction.query.filter_by(return_request_id=rrt.id).first()
        assert rf is not None and rf.status == 'failed'


def test_multi_seller_products_and_orders():
    app = create_app()
    with app.app_context():
        s2 = User.query.filter_by(email='seller2@market.com').first()
        s3 = User.query.filter_by(email='seller3@market.com').first()
        assert s2 is not None and s3 is not None
        p_s2 = Product.query.filter_by(product_ref='S2-001').first()
        p_s3 = Product.query.filter_by(product_ref='S3-001').first()
        assert p_s2 is not None and p_s2.seller_id == s2.id
        assert p_s3 is not None and p_s3.seller_id == s3.id
        o1 = Order.query.filter_by(order_ref='ORD-3001').first()
        o2 = Order.query.filter_by(order_ref='ORD-3002').first()
        assert o1 is not None and o2 is not None
