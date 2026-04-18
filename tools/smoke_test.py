from eacis.app import create_app
from eacis.models.user import User

app = create_app()
with app.app_context():
    try:
        cnt = User.query.filter_by(role='seller').count()
        print('seller_count', cnt)
    except Exception as e:
        print('Error running query:', e)
        raise
