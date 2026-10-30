import py_compile, traceback
try:
    py_compile.compile('eacis/app.py', doraise=True)
    print('compiled ok')
except Exception as e:
    traceback.print_exc()
    print('error:', e)
