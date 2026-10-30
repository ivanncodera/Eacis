import ast, sys, traceback

try:
    with open('eacis/app.py', 'r', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src)
    print('PARSE OK')
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
