import traceback
import sys

path = 'eacis/app.py'
try:
    with open(path, 'rb') as f:
        src = f.read().decode('utf-8')
    compile(src, path, 'exec')
    print('OK: compiled', path)
except Exception:
    traceback.print_exc()
    sys.exit(1)
