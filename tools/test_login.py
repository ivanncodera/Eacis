import requests
from bs4 import BeautifulSoup
s = requests.Session()
url = 'http://127.0.0.1:5000/auth/login'
r = s.get(url)
print('GET status', r.status_code)
soup = BeautifulSoup(r.text, 'html.parser')
el = soup.find('input', {'name':'csrf_token'})
csrf = el.get('value') if el else None
print('CSRF token present?', bool(csrf))
payload = {'email':'customer@eacis.ph','password':'customer123','csrf_token': csrf}
r2 = s.post(url, data=payload, allow_redirects=False)
print('POST status', r2.status_code)
print('Location header:', r2.headers.get('Location'))
print('Response text snippet:', r2.text[:300])
