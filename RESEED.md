# Reseeding the development database (demo)

This document explains how to safely back up and re-run the one-shot reseed that creates demo accounts, products, orders, returns, refunds, vouchers, and sample telemetry.

WARNING: The reseed script drops and recreates all tables. Do NOT run on production or against valuable data.

## 1) Backup your current DB

- SQLite (default development):

```powershell
# PowerShell
if (Test-Path eacis_dev.db) { Copy-Item eacis_dev.db eacis_dev.db.bak }

# Bash
cp eacis_dev.db eacis_dev.db.bak
```

- MySQL / MariaDB:

```bash
mysqldump -u $DB_USER -p $DB_NAME > db-backup.sql
```

- Postgres:

```bash
pg_dump -U $DB_USER -d $DB_NAME -f db-backup.sql
```

## 2) Activate your virtualenv and run the reseed

```powershell
# Windows PowerShell
& .\.venv\Scripts\Activate.ps1
python eacis/reset_and_seed.py
```

```bash
# macOS / Linux
source .venv/bin/activate
python eacis/reset_and_seed.py
```

The script will drop and recreate tables and insert demo users, products, orders (ORD-1001..), a return (RRT-1001) and refund (RFND-1001), a voucher (DEMO10), and short telemetry rows.

## 3) Verify the seed

```bash
python eacis/seeds/verify_seed.py
```

This prints counts and sample rows. Note: `verify_seed.py` checks for static image files; if image paths start with `/` the check might show `False` on Windows due to absolute path handling.

## 4) Troubleshooting

- Foreign-key DROP failures on some MySQL setups are already handled by the reseed script (it temporarily disables `FOREIGN_KEY_CHECKS`). If you use another DB and encounter errors, run `db.create_all()` manually:

```python
# quick ad-hoc
python -c "from eacis.app import create_app; from eacis.extensions import db; app=create_app(); with app.app_context(): db.create_all()"
```

- If the reseed script errors about missing tables for optional models, ensure migrations aren't partially applied; try `db.create_all()` as above and re-run.

## 5) Restore from backup

- SQLite:

```powershell
# PowerShell
if (Test-Path eacis_dev.db.bak) { Copy-Item eacis_dev.db.bak -Destination eacis_dev.db -Force }
```

- MySQL / Postgres: use `mysql` or `psql` to restore from the SQL dump.

---

If you want, I can:
- Add a small `eacis/scripts/verify_and_report.py` that prints additional table counts (orders, return_requests, refund_transactions, vouchers, tickets) and sample refs; or
- Fix the `verify_seed.py` image-path check so it's robust on Windows.

Which would you like next?