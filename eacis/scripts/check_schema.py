from eacis.app import create_app
from eacis.extensions import db
from sqlalchemy import inspect
import os

def check_schema():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('users')]
        print("Existing columns in 'users' table:")
        for col in columns:
            print(f"- {col}")

if __name__ == "__main__":
    check_schema()
