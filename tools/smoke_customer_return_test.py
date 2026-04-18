#!/usr/bin/env python3
import os
import sys
import pathlib
import io
from datetime import datetime

# ensure project root is on sys.path so `import eacis` works when run from tools/
pkg_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_root))
from eacis.app import create_app

app = create_app()

with app.app_context():
    try:
        from eacis.extensions import db
    except Exception:
        from extensions import db

    try:
        from eacis.models.user import User
        from eacis.models.order import Order
        from eacis.models.return_request import ReturnRequest
    except Exception:
        from models.user import User
        from models.order import Order
        from models.return_request import ReturnRequest

    db.create_all()

    # Create test customer and order (if not exists)
    customer = User.query.filter_by(email='customer_test@example.com').first()
    if not customer:
        customer = User(email='customer_test@example.com', role='customer', full_name='Test Customer')
        customer.set_password('password')
        db.session.add(customer)
        db.session.commit()

    order_ref = 'TEST-RETURN-001'
    order = Order.query.filter_by(order_ref=order_ref).first()
    if not order:
        order = Order(order_ref=order_ref, customer_id=customer.id, status='delivered', total=100)
        order.delivered_at = datetime.utcnow()
        db.session.add(order)
        db.session.commit()

    # Disable CSRF for test, enable upload debug
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['DEBUG_UPLOADS'] = True
    client = app.test_client()

    # Log in the test customer by setting session keys used by flask-login
    with client.session_transaction() as sess:
        sess['_user_id'] = str(customer.id)
        sess['_fresh'] = True

    # Prepare multipart form with one image file
    data = {
        'order_ref': order_ref,
        'reason_category': 'CHANGE_OF_MIND',
        'description': 'Test return via smoke test',
        'terms_consent': 'yes',
        'privacy_consent': 'yes'
    }
    files = {'evidence_images': (io.BytesIO(b'\xff\xd8\xff'), 'evidence.jpg')}

    # Perform POST
    resp = client.post('/customer/returns', data={**data, **files})
    print('STATUS', resp.status_code)
    try:
        print('RESP_JSON', resp.get_json())
    except Exception:
        print('RESP_TEXT', resp.get_data(as_text=True)[:1000])

    # Check DB for created return request
    rts = ReturnRequest.query.filter_by(customer_id=customer.id).all()
    print('RETURN_COUNT', len(rts))
    for r in rts:
        print('RRT:', r.rrt_ref, 'STATUS:', r.status, 'EVIDENCE:', r.evidence_urls)

    # List files saved on disk
    upload_dir = os.path.join(app.instance_path, 'uploads', 'returns')
    try:
        print('UPLOAD_DIR_LISTING', os.listdir(upload_dir))
    except Exception as e:
        print('UPLOAD_DIR_ERROR', e)

    # Cleanup: don't remove data; leave it for inspection
