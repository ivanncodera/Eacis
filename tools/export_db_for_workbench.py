"""
Export the application's database for import into external tools (SQL Workbench / MySQL Workbench).

- If using SQLite (default), creates:
  - tools/db-export/eacis_dump.sqlite.sql  (SQL text dump of the SQLite DB)
  - tools/db-export/<table>.csv           (CSV files per table, with header)

- If using another database URL (e.g., MySQL/Postgres), connects via SQLAlchemy and writes CSVs per table.

Run: python tools/export_db_for_workbench.py
"""
import os
import csv
import subprocess
from urllib.parse import urlparse
from pathlib import Path
import sys

# ensure workspace root is on sys.path so 'eacis' package can be imported
workspace_root = Path(__file__).resolve().parents[1]
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from eacis.config import Config

outdir = Path('tools') / 'db-export'
outdir.mkdir(parents=True, exist_ok=True)

cfg = Config()
uri = getattr(cfg, 'SQLALCHEMY_DATABASE_URI', None) or os.getenv('DATABASE_URL')
print(f"Detected DB URI: {uri}")

def export_sqlite(sqlite_path):
    dump_file = outdir / 'eacis_dump.sqlite.sql'
    # create SQL dump using sqlite3 if available
    try:
        print('Creating SQLite SQL dump...')
        with open(dump_file, 'wb') as f:
            subprocess.check_call(['sqlite3', sqlite_path, '.dump'], stdout=f)
        print('SQL dump written to', dump_file)
    except Exception as e:
        print('sqlite3 dump failed:', e)

    # export CSV per table using sqlite3
    try:
        import sqlite3
        conn = sqlite3.connect(sqlite_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            csvf = outdir / f"{t}.csv"
            print('Exporting table', t, '->', csvf)
            cur.execute(f'SELECT * FROM "{t}";')
            rows = cur.fetchall()
            colnames = [d[0] for d in cur.description]
            with open(csvf, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(colnames)
                writer.writerows(rows)
        conn.close()
        print('CSV export complete.')
    except Exception as e:
        print('CSV export failed:', e)


def export_via_sqlalchemy(uri):
    print('Exporting via SQLAlchemy engine...')
    from sqlalchemy import create_engine, inspect, MetaData, Table, select
    engine = create_engine(uri)
    insp = inspect(engine)
    tables = insp.get_table_names()
    metadata = MetaData()
    with engine.connect() as conn:
        for t in tables:
            csvf = outdir / f"{t}.csv"
            print('Exporting table', t, '->', csvf)
            try:
                table = Table(t, metadata, autoload_with=engine)
                sel = select(table)
                res = conn.execute(sel)
                cols = res.keys()
                with open(csvf, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(cols)
                    for row in res:
                        writer.writerow([None if v is None else str(v) for v in row])
            except Exception as e:
                print('Failed to export table', t, '-', e)
    print('SQLAlchemy CSV export complete.')

# Decide path
if not uri:
    print('No DATABASE_URL found in config; aborting.')
else:
    p = urlparse(uri)
    if p.scheme in ('sqlite', ''):
        # handle sqlite:///path or sqlite:///:memory:
        # strip leading sqlite:/// or sqlite:///
        if uri.startswith('sqlite:///'):
            path = uri.replace('sqlite:///', '', 1)
        elif uri.startswith('sqlite://'):
            path = uri.replace('sqlite://', '', 1)
        else:
            path = uri
        path = os.path.expanduser(path)
        if path == ':memory:' or path == '':
            print('In-memory SQLite DB cannot be exported.')
        else:
            if not Path(path).exists():
                print('SQLite DB file not found at', path)
            else:
                export_sqlite(path)
    else:
        # use SQLAlchemy to export
        export_via_sqlalchemy(uri)

print('\nExport finished. Files are in', outdir)
