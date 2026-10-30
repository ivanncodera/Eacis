import pytest

from eacis.app import create_app, db
from eacis.config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_ENABLED = False
    FLASK_ENV = 'development'
    SECRET_KEY = 'test-secret'


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_fullpay_checkout_smoke(app, client):
    # create user and product, add to cart, then perform checkout with full_pay
    from eacis.models.user import User
    from eacis.models.product import Product
    from eacis.models.cart import Cart

    user = User(email='smoke@example.com', first_name='Smoke', last_name='User', role='customer')
    user.set_password('Password123!')
    db.session.add(user)
    db.session.flush()

    prod = Product(product_ref='SMOKE-1', seller_id=1, name='Smoke Product', price=100.0, stock=5, installment_enabled=False)
    db.session.add(prod)
    db.session.flush()

    cart = Cart(user_id=user.id, items=[{'product_id': prod.id, 'qty': 1}])
    db.session.add(cart)
    db.session.commit()

    # login by setting flask-login session directly
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    # perform checkout POST
    resp = client.post('/checkout', data={
        'recipient_name': 'Smoke User',
        'address_line1': '123 Test St',
        'postal_code': '1234',
        'phone': '9912345678',
        'payment': 'full_pay',
        'agree_terms': '1'
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b'Order Confirmed' in resp.data or b'Order Confirmed!' in resp.data