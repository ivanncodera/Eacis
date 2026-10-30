import re
s=open('eacis/app.py','r',encoding='utf-8').read()
tries=len(re.findall(r'^\s*try:\s*$', s, flags=re.M))
excepts=len(re.findall(r'^\s*except\b', s, flags=re.M))
print('tries',tries,'excepts',excepts)
