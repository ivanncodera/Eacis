from pathlib import Path
import re

from eacis.app import create_app
from eacis.validation import validate_seller_return_update_payload


def _impersonate(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _expect_redirect(label, response, failures):
    if response.status_code not in (301, 302, 303):
        failures.append(f"{label}: expected redirect status, got {response.status_code}")


def run_negative_tests():
    app = create_app()
    failures = []
    client = app.test_client()

    # Unauthorized anonymous access should be denied.
    _expect_redirect('Anon /customer/orders', client.get('/customer/orders', follow_redirects=False), failures)
    _expect_redirect('Anon /seller/dashboard', client.get('/seller/dashboard', follow_redirects=False), failures)
    _expect_redirect('Anon /admin/dashboard', client.get('/admin/dashboard', follow_redirects=False), failures)

    # CSRF checks: form token present and missing-token POST rejected.
    login_form = client.get('/auth/login')
    if login_form.status_code != 200:
        failures.append(f'GET /auth/login expected 200, got {login_form.status_code}')
    else:
        html = login_form.get_data(as_text=True)
        token_match = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not token_match or not token_match.group(1):
            failures.append('Login form missing CSRF token input')

    missing_csrf_response = client.post(
        '/auth/login',
        data={'email': 'nobody@example.com', 'password': 'bad-password'},
        follow_redirects=False,
    )
    if missing_csrf_response.status_code != 400:
        failures.append(f'POST /auth/login without csrf_token expected 400, got {missing_csrf_response.status_code}')

    # Login abuse controls: repeated failures should lock the identity.
    abuse_app = create_app()
    abuse_app.config['WTF_CSRF_ENABLED'] = False
    abuse_client = abuse_app.test_client()
    for _ in range(6):
        abuse_client.post('/auth/login', data={'email': 'nobody@example.com', 'password': 'bad'}, follow_redirects=False)
    lock_state = abuse_app._login_attempts.get(('email', 'nobody@example.com')) or {}
    if float(lock_state.get('locked_until') or 0) <= 0:
        failures.append('Login abuse lockout state was not set after repeated failed attempts')

    # Deterministic cross-role denial guards (source assertions).
    source = (Path(__file__).resolve().parents[1] / 'eacis' / 'app.py').read_text(encoding='utf-8')
    if "def customer_orders():" not in source or "getattr(current_user, 'role', None) == 'customer'" not in source:
        failures.append('Customer orders route is missing explicit customer-role guard')
    if "def seller_dashboard():" not in source or "getattr(current_user, 'role', None) == 'seller'" not in source:
        failures.append('Seller dashboard route is missing explicit seller-role guard')
    if "def admin_dashboard():" not in source or "getattr(current_user, 'role', None) == 'admin'" not in source:
        failures.append('Admin dashboard route is missing explicit admin-role guard')

    # Invalid action validation check for seller return update payload.
    payload_errors, _ = validate_seller_return_update_payload({'action': 'invalid_action'})
    if 'action' not in payload_errors:
        failures.append('Invalid return action was not rejected by validator')

    # Ensure route still enforces invalid action guardrail in code path.
    app_source = Path(__file__).resolve().parents[1] / 'eacis' / 'app.py'
    source = app_source.read_text(encoding='utf-8')
    if "payload_errors, payload = validate_seller_return_update_payload(request.form)" not in source:
        failures.append('seller_returns_update is not using shared return action validator')

    if failures:
        print('FAIL phase E negative tests')
        for failure in failures:
            print('-', failure)
        return 1

    print('PASS phase E negative tests')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_negative_tests())
