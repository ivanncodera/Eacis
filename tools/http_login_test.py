import re
import urllib.request, urllib.parse, http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

r = opener.open('http://127.0.0.1:5000/auth/login')
html = r.read().decode(errors='ignore')
print('GET status', r.getcode())
ms = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html, re.I)
csrf = ms.group(1) if ms else None
print('csrf?', bool(csrf))
post_data = urllib.parse.urlencode({'email':'customer@eacis.ph','password':'customer123','csrf_token': csrf}).encode()
resp = opener.open('http://127.0.0.1:5000/auth/login', data=post_data)
print('POST status', resp.getcode())
print('Location:', resp.geturl())
print('Body snippet:', resp.read(300))
