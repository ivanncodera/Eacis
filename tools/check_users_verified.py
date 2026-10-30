from eacis.app import create_app
app = create_app()
with app.app_context():
    from eacis.models.user import User
    users = User.query.order_by(User.id).all()
    print('Users and email_verified_at:')
    for u in users:
        print(u.email, '->', bool(getattr(u, 'email_verified_at', None)))
