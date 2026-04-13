import sys
import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

def inspect_db():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not found in .env")
        return
    
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    print("Tables in database:")
    tables = inspector.get_table_names()
    for table in tables:
        print(f"- {table}")
        if table == 'users':
            print("  Columns in 'users':")
            columns = inspector.get_columns('users')
            for col in columns:
                print(f"    - {col['name']}")

if __name__ == "__main__":
    inspect_db()
