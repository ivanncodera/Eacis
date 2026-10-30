import sys, pathlib
sys.path.insert(0, str(pathlib.Path('.').resolve()))
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

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    resp = client.post('/checkout', data={
        'recipient_name': 'Smoke User',
        'address_line1': '123 Test St',
        'postal_code': '1234',
        'phone': '9912345678',
        'payment': 'full_pay',
        'agree_terms': '1'
    }, follow_redirects=True)

    print('STATUS', resp.status_code)
    try:
        print('FINAL PATH:', getattr(resp, 'request', {}).get('path') if isinstance(getattr(resp, 'request', None), dict) else getattr(resp, 'request', {}).get('path') if hasattr(resp, 'request') else None)
    except Exception:
        pass
    try:
        # Flask test response exposes request context in resp.request.environ on some versions
        if hasattr(resp, 'request') and getattr(resp, 'request', None):
            try:
                print('REQUEST REPR:', repr(resp.request))
            except Exception:
                pass
    except Exception:
        pass
    text = resp.get_data(as_text=True)
    print('HAS Order Confirmed:', 'Order Confirmed' in text or 'Order Confirmed!' in text)
    # show common error snippets
    snippets = []
    for token in ['You must agree to the Terms', 'form-error', 'checkout_errors', 'error', 'Invalid', 'Order not found', 'Installment not available']:
        if token in text:
            snippets.append(token)
    print('SNIPPETS:', snippets)
    # print a middle portion where form errors typically appear
    start = text.find('<form')
    if start != -1:
        print(text[start:start+4000])
    else:
        print(text[:4000])
        # print any form-error blocks
        idx = 0
        while True:
            i = text.find('form-error', idx)
            if i == -1:
                break
            snippet = text[max(0, i-120):i+120]
            print('\n--- form-error snippet ---\n', snippet)
            idx = i+1
            # extract textual messages inside form-error divs
            import re
            errs = re.findall(r'<div class="form-error"[^>]*>(.*?)</div>', text, flags=re.DOTALL)
            if errs:
                print('\n=== Extracted form-error messages ===')
                for e in errs:
                    cleaned = re.sub(r'<[^>]+>', '', e).strip()
                    print('-', cleaned[:200])
            # look for checkout.general errors
            if 'Could not place your order' in text:
                i = text.find('Could not place your order')
                print('\n--- Checkout error context ---\n', text[max(0, i-120):i+200])
