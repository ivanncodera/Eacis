from eacis.app import create_app, db as app_db
import importlib, sys

app = create_app()
with app.app_context():
    print('app_db id:', id(app_db))
    try:
        m = importlib.import_module('eacis.models.user')
        print('User model module:', m.__name__)
        for name, val in m.__dict__.items():
            if getattr(val, '__class__', None) and val.__class__.__name__ == 'SQLAlchemy':
                print('User module SQLAlchemy object:', name, id(val))
    except Exception as e:
        print('inspect error:', e)

    sa_objs = []
    for name, mod in list(sys.modules.items()):
        if not mod:
            continue
        if hasattr(mod, '__dict__'):
            for v in mod.__dict__.values():
                if getattr(v, '__class__', None) and v.__class__.__name__ == 'SQLAlchemy':
                    sa_objs.append((name, id(v)))
    print('Found SQLAlchemy instances (module, id):')
    for item in sa_objs:
        print(' ', item)
