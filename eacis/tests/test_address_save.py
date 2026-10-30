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


def test_save_address_api(app, client):
    from eacis.models.user import User
    from eacis.models.address import Address

    user = User(email='addrtest@example.com', first_name='Addr', last_name='Test', role='customer')
    user.set_password('Password123!')
    db.session.add(user)
    db.session.flush()
    db.session.commit()

    # login by setting flask-login session directly
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    data = {
        'recipient_name': 'Addr Test',
        'phone': '09171234567',
        'house_number': '12A',
        'address_line1': '123 Test St',
        'barangay': 'Capitol',
        'city_municipality': 'Laoag',
        'province': 'Ilocos Norte',
        'region': 'Region I',
        'postal_code': '2900',
        'label': 'Home'
    }

    resp = client.post('/customer/addresses/save', data=data, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 200
    j = resp.get_json()
    assert j['status'] == 'ok'
    # verify persisted
    a = Address.query.filter_by(user_id=user.id).first()
    assert a is not None
    assert a.house_number == '12A'
    assert a.landmark is None or a.landmark == ''
    assert a.phone and a.phone.startswith('0')
