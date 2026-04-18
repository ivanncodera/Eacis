import ast
p='eacis/services/otp_service.py'
with open(p,'r', encoding='utf-8') as f:
    s = f.read()
try:
    ast.parse(s)
    print('PARSE_OK')
except SyntaxError as e:
    print('SyntaxError:', e)
    try:
        print('Line content repr:', repr(s.splitlines()[e.lineno-1]))
    except Exception:
        pass
