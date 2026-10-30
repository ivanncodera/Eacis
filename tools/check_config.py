from eacis.app import create_app
app = create_app()
print('WTF_CSRF_SSL_STRICT ->', app.config.get('WTF_CSRF_SSL_STRICT'))
print('PREFERRED_URL_SCHEME ->', app.config.get('PREFERRED_URL_SCHEME'))
print('WTF_CSRF_ENABLED ->', app.config.get('WTF_CSRF_ENABLED'))
