import ast
import sys

path = 'eacis/app.py'
try:
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src)
    print('OK: AST parsed')
except SyntaxError as e:
    print('SyntaxError:', e.msg)
    print('File:', e.filename)
    print('Line:', e.lineno)
    print('Offset:', e.offset)
    # print the offending line
    lines = src.splitlines()
    if 1 <= e.lineno <= len(lines):
        print('Code:', lines[e.lineno - 1])
    sys.exit(1)
except Exception as e:
    print('Other error:', type(e), e)
    sys.exit(1)
