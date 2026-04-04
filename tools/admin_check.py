import sys, pathlib
proj_root = pathlib.Path(__file__).resolve().parent.parent
if str(proj_root) not in sys.path:
    sys.path.insert(0, str(proj_root))

try:
    from eacis.app import create_app
except Exception:
    # fallback: try importing as module-less script
    sys.path.insert(0, str(proj_root / 'eacis'))
    from app import create_app

app = create_app()
client = app.test_client()

paths = ['/admin/refunds','/admin/sellers','/admin/audit']

for p in paths:
    print(f'Checking {p}...')
    rv = client.get(p)
    if rv.status_code != 200:
        print('  HTTP', rv.status_code)
        continue
    html = rv.get_data(as_text=True)
    if p.endswith('refunds'):
        print('  refunds-table:', 'refunds-table' in html and 'OK' or 'MISSING')
        print('  export-refunds-csv:', 'export-refunds-csv' in html and 'OK' or 'MISSING')
        print('  refunds.js:', '/static/js/admin/refunds.js' in html and 'OK' or 'MISSING')
    if p.endswith('sellers'):
        print('  sellers-table:', 'sellers-table' in html and 'OK' or 'MISSING')
        print('  export-sellers-csv:', 'export-sellers-csv' in html and 'OK' or 'MISSING')
        print('  sellers.js:', '/static/js/admin/sellers.js' in html and 'OK' or 'MISSING')
    if p.endswith('audit'):
        print('  audit-table:', 'audit-table' in html and 'OK' or 'MISSING')
        print('  audit.js:', '/static/js/admin/audit.js' in html and 'OK' or 'MISSING')

print('\nStatic assets checks:')
for s in ['/static/js/components/topbar.js','/static/js/admin/refunds.js','/static/assets/icons/menu.svg']:
    rv = client.get(s)
    print(f'  {s}:', rv.status_code)

print('\nDone')