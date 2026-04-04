from eacis.app import create_app, db as app_db

app = create_app()
with app.app_context():
    print('app id:', id(app), 'app.name:', getattr(app, 'name', None), 'import_name:', getattr(app, 'import_name', None))
    print('app_db id:', id(app_db))
    # expose common internals
    for attr in ('app','_app','get_app','engines','_state','bind','model_changes'):
        try:
            val = getattr(app_db, attr)
        except Exception as e:
            val = f'error: {e}'
        print(f'app_db.{attr}:', val)
    # try calling get_app if present
    if hasattr(app_db, 'get_app') and callable(app_db.get_app):
        try:
            ga = app_db.get_app()
            print('app_db.get_app() id:', id(ga), 'name:', getattr(ga,'name',None))
        except Exception as e:
            print('get_app() raised:', e)
    # Check Flask-SQLAlchemy _state
    try:
        st = getattr(app_db, '_state')
        print('_state:', type(st), repr(st)[:200])
    except Exception as e:
        print('_state error:', e)
