#!/usr/bin/env python
"""Run Flask-Migrate upgrade() using the app factory."""
import sys
import pathlib
# Ensure project root is on sys.path so `import eacis` works when running this script
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app

def main():
    app = create_app()
    with app.app_context():
        try:
            # Import here to ensure Flask-Migrate is available in the app context
            from flask_migrate import upgrade
            # When multiple heads exist, upgrade to all heads
            upgrade(revision='heads')
            print('Migrations applied (upgrade head)')
        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    main()
