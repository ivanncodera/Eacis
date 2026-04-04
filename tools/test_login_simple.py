from eacis.app import create_app
import re

app = create_app()
with app.test_client() as c:
    r = c.get('/auth/login')
    print('GET status', r.status_code)
    html = r.data.decode(errors='ignore')
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html, re.I)
    csrf = m.group(1) if m else None
    print('CSRF token present?', bool(csrf))
    payload = {'email':'customer@eacis.ph','password':'customer123','csrf_token': csrf}
    r2 = c.post('/auth/login', data=payload, follow_redirects=False)
    print('POST status', r2.status_code)
    print('Location header:', r2.headers.get('Location'))
    print('Response text snippet:', r2.data.decode()[:300])
