#!/usr/bin/env python
"""Reseed the dev database with demo scenarios, then run pytest.

Usage:
    python tools/reseed_and_run_tests.py
"""
import subprocess
import sys

# Ensure working directory is project root
from pathlib import Path
proj_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(proj_root))

try:
    from eacis.reset_and_seed import seed_database
except Exception:
    from reset_and_seed import seed_database


def main():
    print('Running reseed...')
    seed_database()
    print('\nRe-seed complete. Running pytest...')
    rc = subprocess.call([sys.executable, '-m', 'pytest', '-q'])
    if rc != 0:
        print('\nTests failed with exit code', rc)
    else:
        print('\nAll tests passed')
    sys.exit(rc)


if __name__ == '__main__':
    main()
