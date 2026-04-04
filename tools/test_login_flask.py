from eacis.app import create_app
from bs4 import BeautifulSoup

app = create_app()
with app.test_client() as c:
    r = c.get('/auth/login')
    print('GET status', r.status_code)
    soup = BeautifulSoup(r.data, 'html.parser')
    el = soup.find('input', {'name':'csrf_token'})
    csrf = el.get('value') if el else None
    print('CSRF token present?', bool(csrf))
    payload = {'email':'customer@eacis.ph','password':'customer123','csrf_token': csrf}
    r2 = c.post('/auth/login', data=payload, follow_redirects=False)
    print('POST status', r2.status_code)
    print('Location header:', r2.headers.get('Location'))
    print('Response text snippet:', r2.data.decode()[:300])
