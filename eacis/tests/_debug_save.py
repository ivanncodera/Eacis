import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from eacis.app import create_app, db
from eacis.config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_ENABLED = False
    FLASK_ENV = 'development'
    SECRET_KEY = 'test-secret'

app = create_app(TestConfig)
with app.app_context():
    db.create_all()
    from eacis.models.user import User
    user = User(email='addrtest@example.com', first_name='Addr', last_name='Test', role='customer')
    user.set_password('Password123!')
    db.session.add(user)
    db.session.flush()
    db.session.commit()

    client = app.test_client()
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
    print('status:', resp.status_code)
    try:
        print('json:', resp.get_json())
    except Exception:
        print('raw:', resp.get_data(as_text=True))
