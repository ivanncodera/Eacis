#!/usr/bin/env python
"""Smoke test: create a customer, login, create an address, fetch the addresses API."""
import sys
import pathlib
import re
from datetime import datetime

project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app
from eacis.extensions import db
from eacis.models.user import User


def extract_csrf(html):
    m = re.search(r'name=["\']csrf_token["\'] value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


def main():
    app = create_app()
    with app.app_context():
        # ensure dev user exists and is verified
        user = User.query.filter_by(email='customer@example.com').first()
        if not user:
            user = User(email='customer@example.com', role='customer', full_name='Dev Customer')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
        # mark email verified so login succeeds
        if not getattr(user, 'email_verified_at', None):
            user.email_verified_at = datetime.utcnow()
            db.session.commit()

        client = app.test_client()

        # login
        # fetch login page to get CSRF token
        rv = client.get('/auth/login')
        login_html = rv.get_data(as_text=True)
        login_csrf = extract_csrf(login_html)
        print('login page status', rv.status_code, 'csrf found', bool(login_csrf))
        if login_csrf:
            print('csrf token:', login_csrf[:10] + '...')
        headers_login = {'Referer': 'http://127.0.0.1:5000/auth/login', 'Host': '127.0.0.1:5000'}
        rv = client.post('/auth/login', data={'email': 'customer@example.com', 'password': 'password', 'csrf_token': login_csrf}, follow_redirects=True, headers=headers_login)
        print('login status', rv.status_code)
        if rv.status_code != 302 and rv.status_code != 200:
            print('login response snippet:', rv.get_data(as_text=True)[:800])

        # open addresses page to get CSRF
        rv = client.get('/customer/addresses/')
        html = rv.get_data(as_text=True)
        csrf = extract_csrf(html)
        print('got addresses page', rv.status_code, 'csrf?', bool(csrf))

        form = {
            'action': 'save',
            'csrf_token': csrf,
            'label': 'Home test',
            'recipient_name': 'Dev Customer',
            'phone': '9123456789',
            'postal_code': '1000',
            'address_line1': '123 Test St',
            'barangay': 'Test Brgy',
            'city_municipality': 'Manila',
            'province': 'Metro Manila',
            'set_default': '1',
            'lat': '14.6',
            'lng': '120.98'
        }
        headers_addr = {'Referer': 'http://127.0.0.1:5000/customer/addresses/', 'Host': '127.0.0.1:5000'}
        rv = client.post('/customer/addresses/save', data=form, follow_redirects=True, headers=headers_addr)
        print('save address status', rv.status_code)

        rv = client.get('/customer/addresses/api')
        print('api status', rv.status_code)
        try:
            print('api json:', rv.get_json())
        except Exception:
            print('api text:', rv.get_data(as_text=True)[:500])


if __name__ == '__main__':
    main()
