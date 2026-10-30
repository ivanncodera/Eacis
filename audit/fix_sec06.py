import os

def add_csrf(path, form_marker):
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    c_norm = c.replace('\r\n', '\n')
    if '<input type="hidden" name="csrf_token"' in c_norm:
        print(f"CSRF already in {path}")
        return
    old = f"{form_marker}\n                  <input type=\"hidden\" name=\"revoke_id\""
    new = f"{form_marker}\n                  <input type=\"hidden\" name=\"csrf_token\" value=\"{{{{ csrf_token() }}}}\">\n                  <input type=\"hidden\" name=\"revoke_id\""
    if old in c_norm:
        c_new = c_norm.replace(old, new)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c_new)
        print(f"Added CSRF to {path}")
    else:
        print(f"Could not find marker in {path}")

cust_path = os.path.join('eacis', 'templates', 'customer', 'trusted_devices.html')
admin_path = os.path.join('eacis', 'templates', 'admin', 'trusted_devices.html')

add_csrf(cust_path, '<form method="post" style="display:inline" data-confirm="Revoke this trusted device?">')
add_csrf(admin_path, '<form method="post" style="display:inline" data-enhance="submit-loading" data-confirm="Revoke trusted device #{{ d.id }}?">')
