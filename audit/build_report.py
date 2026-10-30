import os
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
with open(os.path.join(ROOT, 'audit', 'routes_inventory.json'), 'r', encoding='utf-8') as f:
    routes_inv = json.load(f)
with open(os.path.join(ROOT, 'audit', 'models_inventory.json'), 'r', encoding='utf-8') as f:
    models_inv = json.load(f)
with open(os.path.join(ROOT, 'audit', 'static_audit_summary.json'), 'r', encoding='utf-8') as f:
    static_sum = json.load(f)
with open(os.path.join(ROOT, 'audit', 'logs', 'dynamic_audit_results.json'), 'r', encoding='utf-8') as f:
    dyn_res = json.load(f)

print(f"Loaded {len(routes_inv)} routes, {len(models_inv)} models.")
