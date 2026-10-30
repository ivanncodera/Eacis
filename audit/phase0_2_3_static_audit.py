import os
import sys
import ast
import re
import json
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\Ivann\Downloads\Eacis")
AUDIT_DIR = ROOT / "audit"
AUDIT_DB = ROOT / "instance" / "audit_copy.db"

os.environ["DATABASE_URL"] = f"sqlite:///{AUDIT_DB.as_posix()}"
os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{AUDIT_DB.as_posix()}"
os.environ["MAIL_MODE"] = "file"
os.environ["MAIL_OUTPUT_DIR"] = str(AUDIT_DIR / "logs" / "mail")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eacis"))

import eacis.app as app_module
from eacis.app import create_app
from eacis.extensions import db

app = create_app()
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{AUDIT_DB.as_posix()}"
app.config["MAIL_MODE"] = "file"
app.config["MAIL_OUTPUT_DIR"] = str(AUDIT_DIR / "logs" / "mail")

report_data = {}

# 1. Inspect AST of eacis/app.py
app_py_path = ROOT / "eacis" / "app.py"
app_source = app_py_path.read_text(encoding="utf-8", errors="replace")
app_lines = app_source.splitlines()
tree = ast.parse(app_source, filename="eacis/app.py")

func_defs = []
duplicate_funcs = {}
seen_funcs = {}
bare_excepts = []
commits_in_loops = []
utcnow_lines = []
float_money_lines = []

for i, line in enumerate(app_lines, 1):
    if "datetime.utcnow" in line:
        utcnow_lines.append(i)
    if re.search(r"float\([^)]*(price|total|amount|subtotal|discount|fee|tax|balance|installment|refund|penalty)", line, re.I):
        float_money_lines.append((i, line.strip()))

for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        end_line = getattr(node, "end_lineno", node.lineno)
        length = end_line - node.lineno + 1
        decos = [ast.unparse(d) for d in node.decorator_list]
        if node.name in seen_funcs:
            duplicate_funcs.setdefault(node.name, [seen_funcs[node.name]]).append(node.lineno)
        seen_funcs[node.name] = node.lineno
        func_defs.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": end_line,
            "length": length,
            "decorators": decos,
        })
        # Check for commits inside loops
        for sub in ast.walk(node):
            if isinstance(sub, (ast.For, ast.While)):
                for inner in ast.walk(sub):
                    if isinstance(inner, ast.Call) and "db.session.commit" in ast.unparse(inner):
                        commits_in_loops.append({
                            "func": node.name,
                            "loop_line": sub.lineno,
                            "commit_line": inner.lineno
                        })
    elif isinstance(node, ast.ExceptHandler):
        body_src = [ast.unparse(stmt) for stmt in node.body]
        has_rollback = any("rollback" in s for s in body_src)
        is_swallowed = (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)) or (
            all(isinstance(s, (ast.Pass, ast.Expr)) for s in node.body) and not any("log" in s or "flash" in s or "abort" in s for s in body_src)
        )
        if is_swallowed or not has_rollback:
            bare_excepts.append({
                "lineno": node.lineno,
                "type": ast.unparse(node.type) if node.type else "bare_except",
                "is_swallowed": is_swallowed,
                "has_rollback": has_rollback,
                "body": body_src[:2]
            })

func_defs_sorted = sorted(func_defs, key=lambda x: x["length"], reverse=True)

# 2. Route Inventory
routes = []
func_by_name = {f["name"]: f for f in func_defs}
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    methods = sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS"))
    vf = app.view_functions.get(rule.endpoint)
    lineno = None
    decos = []
    if vf and hasattr(vf, "__code__"):
        lineno = vf.__code__.co_firstlineno
    if rule.endpoint in func_by_name:
        decos = func_by_name[rule.endpoint]["decorators"]
        if not lineno:
            lineno = func_by_name[rule.endpoint]["lineno"]
    routes.append({
        "rule": rule.rule,
        "methods": methods,
        "endpoint": rule.endpoint,
        "lineno": lineno,
        "decorators": decos,
    })

# 3. Template Checks: url_for targets, forms missing csrf_token, |safe usage, innerHTML usage
templates_dir = ROOT / "eacis" / "templates"
registered_endpoints = {r["endpoint"] for r in routes} | {"static"}
broken_url_for = []
forms_missing_csrf = []
xss_safe_usages = []
xss_innerhtml_usages = []

for tpl in sorted(templates_dir.rglob("*.html")):
    rel = tpl.relative_to(ROOT).as_posix()
    txt = tpl.read_text(encoding="utf-8", errors="replace")
    # url_for
    for m in re.finditer(r"url_for\(\s*['\"]([^'\"]+)['\"]", txt):
        ep = m.group(1)
        line_num = txt[:m.start()].count("\n") + 1
        if ep not in registered_endpoints:
            broken_url_for.append({"file": rel, "line": line_num, "endpoint": ep})
    # <form method="post"> without csrf_token
    for m in re.finditer(r"<form\b([^>]*)>(.*?)</form>", txt, re.I | re.S):
        attrs, inner = m.group(1), m.group(2)
        if re.search(r"method\s*=\s*['\"]?post['\"]?", attrs, re.I):
            if "csrf_token" not in inner:
                line_num = txt[:m.start()].count("\n") + 1
                forms_missing_csrf.append({"file": rel, "line": line_num, "attrs": attrs.strip()})
    # |safe
    for m in re.finditer(r"\|\s*safe\b", txt):
        line_num = txt[:m.start()].count("\n") + 1
        line_str = txt.splitlines()[line_num - 1].strip()
        if "tojson" not in line_str:
            xss_safe_usages.append({"file": rel, "line": line_num, "code": line_str[:120]})
    # innerHTML
    for m in re.finditer(r"\.innerHTML\s*=", txt):
        line_num = txt[:m.start()].count("\n") + 1
        line_str = txt.splitlines()[line_num - 1].strip()
        xss_innerhtml_usages.append({"file": rel, "line": line_num, "code": line_str[:120]})

for js in sorted((ROOT / "eacis" / "static" / "js").rglob("*.js")):
    rel = js.relative_to(ROOT).as_posix()
    txt = js.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"\.innerHTML\s*=", txt):
        line_num = txt[:m.start()].count("\n") + 1
        line_str = txt.splitlines()[line_num - 1].strip()
        xss_innerhtml_usages.append({"file": rel, "line": line_num, "code": line_str[:120]})

# 4. Schema vs SQLAlchemy Metadata check on audit_copy.db
conn = sqlite3.connect(str(AUDIT_DB))
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
actual_tables = {r[0] for r in cur.fetchall()}

model_tables = {}
schema_diffs = []
missing_fk_indexes = []

with app.app_context():
    for tname, table in db.metadata.tables.items():
        cols = {c.name: str(c.type) for c in table.columns}
        fks = [f"{c.name} -> {fk.target_fullname}" for c in table.columns for fk in c.foreign_keys]
        idxs = [ix.name for ix in table.indexes]
        model_tables[tname] = {"columns": cols, "foreign_keys": fks, "indexes": idxs}
        if tname not in actual_tables:
            schema_diffs.append({"table": tname, "issue": "Table in SQLAlchemy metadata missing from DB"})
        else:
            cur.execute(f"PRAGMA table_info('{tname}')")
            db_cols = {r[1]: r[2] for r in cur.fetchall()}
            cur.execute(f"PRAGMA index_list('{tname}')")
            db_idx_names = [r[1] for r in cur.fetchall()]
            indexed_cols = set()
            for ixn in db_idx_names:
                cur.execute(f"PRAGMA index_info('{ixn}')")
                for ir in cur.fetchall():
                    indexed_cols.add(ir[2])
            for cname in cols:
                if cname not in db_cols:
                    schema_diffs.append({"table": tname, "issue": f"Column '{cname}' in model missing from DB table"})
            for cname in db_cols:
                if cname not in cols:
                    schema_diffs.append({"table": tname, "issue": f"Column '{cname}' in DB table not mapped in model"})
            # Check foreign keys without indexes
            for c in table.columns:
                if c.foreign_keys and c.name not in indexed_cols and not c.primary_key and not c.unique:
                    missing_fk_indexes.append({"table": tname, "column": c.name})

conn.close()

summary = {
    "app_py_total_lines": len(app_lines),
    "total_functions_in_app_py": len(func_defs),
    "top_15_largest_functions": func_defs_sorted[:15],
    "duplicate_functions": duplicate_funcs,
    "swallowed_or_no_rollback_excepts_count": len(bare_excepts),
    "swallowed_excepts": [b for b in bare_excepts if b["is_swallowed"]],
    "commits_in_loops": commits_in_loops,
    "utcnow_count": len(utcnow_lines),
    "utcnow_sample_lines": utcnow_lines[:20],
    "float_money_count": len(float_money_lines),
    "float_money_sample": float_money_lines[:25],
    "total_routes": len(routes),
    "broken_url_for": broken_url_for,
    "forms_missing_csrf": forms_missing_csrf,
    "xss_safe_usages": xss_safe_usages,
    "xss_innerhtml_usages": xss_innerhtml_usages,
    "model_tables_count": len(model_tables),
    "actual_db_tables_count": len(actual_tables),
    "schema_diffs": schema_diffs,
    "missing_fk_indexes": missing_fk_indexes,
}

(AUDIT_DIR / "static_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(AUDIT_DIR / "routes_inventory.json").write_text(json.dumps(routes, indent=2), encoding="utf-8")
(AUDIT_DIR / "models_inventory.json").write_text(json.dumps(model_tables, indent=2), encoding="utf-8")
print(json.dumps({
    "app_py_lines": len(app_lines),
    "total_routes": len(routes),
    "total_models": len(model_tables),
    "broken_url_for_count": len(broken_url_for),
    "forms_missing_csrf_count": len(forms_missing_csrf),
    "swallowed_excepts_count": len([b for b in bare_excepts if b["is_swallowed"]]),
    "commits_in_loops_count": len(commits_in_loops),
    "float_money_count": len(float_money_lines),
    "schema_diffs_count": len(schema_diffs),
    "missing_fk_indexes_count": len(missing_fk_indexes),
}, indent=2))
