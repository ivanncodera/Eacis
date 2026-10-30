#!/usr/bin/env python
"""Stamp all revision files found under migrations/versions as applied.

Use when the DB already contains objects created outside alembic and you want
to bring alembic's version table in sync without executing SQL.
"""
import sys
import pathlib
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from eacis.app import create_app

import re

def list_revisions(dirpath):
    p = pathlib.Path(dirpath)
    if not p.exists():
        return []
    revs = []
    pattern = re.compile(r"^revision\s*=\s*['\"]([0-9a-fA-F_\-]+)['\"]", re.M)
    for f in sorted(p.iterdir()):
        if f.suffix != '.py':
            continue
        try:
            content = f.read_text(encoding='utf-8')
            m = pattern.search(content)
            if m:
                revs.append(m.group(1))
        except Exception:
            continue
    return revs

def main():
    app = create_app()
    with app.app_context():
        from flask_migrate import stamp
        vdir = project_root / 'migrations' / 'versions'
        revs = list_revisions(vdir)
        if not revs:
            print('No revisions found in', vdir)
            return
        for r in revs:
            try:
                stamp(revision=r)
                print('Stamped', r)
            except Exception as e:
                print('Failed to stamp', r, '-', e)

if __name__ == '__main__':
    main()
