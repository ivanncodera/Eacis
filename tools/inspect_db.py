from eacis.app import create_app, db as app_db
from importlib import import_module

app = create_app()
with app.app_context():
    print('app_db id:', id(app_db))
    try:
        m = import_module('eacis.models.user')
        User = getattr(m, 'User')
        # find the db object referenced in model module (search globals)
        model_db = None
        for v in m.__dict__.values():
            if getattr(v, '__class__', None) and v.__class__.__name__ == 'SQLAlchemy':
                model_db = v
                break
        # explicit attempt: check User.__dict__ for metadata.bind
        print('User model module:', m.__name__)
        print('User query class db id (via User.query.session._bind):', end=' ')
        try:
            sess = User.query.session
            bind = sess.get_bind()
            print('bind engine:', bind)
        except Exception as e:
            print('could not get bind:', e)
        print('app in app_db.engines?', app in getattr(app_db, 'engines', {}))
        print('app_db.engines keys:', list(getattr(app_db, 'engines', {}).keys()))
    except Exception as e:
        print('Error inspecting User model:', e)

    # Also show all SQLAlchemy instances found in sys.modules
    import sys
    sa_objs = []
    for name, mod in list(sys.modules.items()):
        if not mod:
            continue
        if hasattr(mod, '__dict__'):
            for v in mod.__dict__.values():
                if getattr(v, '__class__', None) and v.__class__.__name__ == 'SQLAlchemy':
                    sa_objs.append((name, id(v)))
    print('Found SQLAlchemy instances in modules (module, id):')
    for item in sa_objs:
        print(' ', item)
