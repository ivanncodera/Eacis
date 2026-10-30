import ast, sys
try:
    with open('eacis/app.py', 'r', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src, 'eacis/app.py')
    print('parsed ok')
except SyntaxError as e:
    print('SyntaxError:', e.msg, 'at line', e.lineno, 'col', e.offset)
    try:
        lines = src.splitlines()
        start = max(1, e.lineno - 3)
        end = min(len(lines), e.lineno + 3)
        for i in range(start, end + 1):
            prefix = '>' if i == e.lineno else ' '
            print(f"{prefix} {i:4d}: {lines[i-1]}")
    except Exception:
        pass
    sys.exit(1)
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(2)
