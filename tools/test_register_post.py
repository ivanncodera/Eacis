import re
import sys
import runpy

# Ensure package imports resolve
sys.path.insert(0, '.')
from eacis.app import create_app

app = create_app()
client = app.test_client()

# GET register page to get CSRF token
res = client.get('/auth/register/customer')
html = res.get_data(as_text=True)
match = re.search(r'name="csrf_token" value="([^"]+)"', html)
if not match:
    print('No csrf token found in form')
    print(html[:1000])
    sys.exit(1)
csrf = match.group(1)
print('csrf token:', csrf)

email = 'autotest_register_20260419@example.com'
form = {
    'csrf_token': csrf,
    'role': 'customer',
    'first_name': 'Auto',
    'last_name': 'Tester',
    'email': email,
    'phone': '09171234567',
    'address_line1': '123 Test St',
    'barangay': 'Test Brgy',
    'city_municipality': 'Test City',
    'province': 'Test Province',
    'postal_code': '1000',
    'password': 'StrongP@ss123',
    'confirm_password': 'StrongP@ss123',
    'terms_consent': 'yes',
    'privacy_consent': 'yes'
}

res2 = client.post('/auth/register/customer', data=form, follow_redirects=False)
print('POST status:', res2.status_code)
print('Location:', res2.headers.get('Location'))
print('Response snippet:')
print(res2.get_data(as_text=True)[:1000])

# Try follow redirect if present
if res2.status_code in (302, 303) and res2.headers.get('Location'):
    loc = res2.headers.get('Location')
    if loc.startswith('/'):
        res3 = client.get(loc)
        print('Redirected page snippet:', res3.get_data(as_text=True)[:1000])

# Check for email file created
import os
mail_path = os.path.join(app.instance_path, 'emails')
if os.path.isdir(mail_path):
    files = sorted(os.listdir(mail_path))
    print('\nEmails in', mail_path, ':', files[-5:])
else:
    print('\nMail path not found:', mail_path)
