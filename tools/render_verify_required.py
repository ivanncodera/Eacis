from eacis.app import create_app
from flask import render_template

app = create_app()
with app.test_request_context('/'):
    html = render_template('auth/verify_required.html', email='customer@demo.com')
    # print a small snippet to confirm csrf token rendered
    snippet = html.split('\n')[:30]
    print('\n'.join(snippet))
