"""Simple accessibility smoke checker using Flask test client.
Checks presence of common ARIA attributes on core components.
"""
from pathlib import Path
import sys
proj_root = Path(__file__).resolve().parent.parent
if str(proj_root) not in sys.path:
    sys.path.insert(0, str(proj_root))

try:
    from eacis.app import create_app
except Exception:
    from app import create_app

app = create_app()
client = app.test_client()

pages = ['/', '/shop', '/admin/refunds', '/admin/sellers', '/admin/audit']

def check_page(path, html):
    results = []
    # topbar checks
    results.append(('topbar role', 'role="banner"' in html or 'class="topbar"' in html))
    results.append(('search aria', 'data-topbar-search-toggle' in html or 'aria-label="Toggle search"' in html))
    results.append(('hamburger aria', 'data-topbar-hamb' in html or 'aria-label="Toggle sidebar"' in html))
    # sidebar
    results.append(('sidebar role', 'role="navigation"' in html or 'class="sidebar"' in html))
    results.append(('sidebar toggle aria', 'data-sidebar-toggle' in html or 'aria-expanded' in html))
    # modal and toasts
    results.append(('modal role', 'role="dialog"' in html or 'modal-overlay' in html))
    results.append(('toast container', 'toast-stack' in html or 'toast-container' in html))
    # buttons aria-label
    results.append(('icon buttons aria', 'aria-label=' in html))
    return results

all_ok = True
for p in pages:
    rv = client.get(p)
    ok = rv.status_code == 200
    print(f'Page {p}: HTTP {rv.status_code}')
    if not ok:
        all_ok = False
        continue
    html = rv.get_data(as_text=True)
    checks = check_page(p, html)
    for name, passed in checks:
        print(f'  {name}:', 'OK' if passed else 'MISSING')
        if not passed: all_ok = False

print('\nSummary:', 'PASS' if all_ok else 'FAIL')
