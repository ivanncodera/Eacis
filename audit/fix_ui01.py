import os

path = os.path.join('eacis', 'templates', 'customer', 'addresses.html')
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

target = """          <div class="address-card__actions">
            <a href="{{ url_for('customer_addresses.edit_address', addr_id=addr.id) }}" class="btn btn--white btn--sm">Edit</a>
            <form method="post" action="{{ url_for('customer_addresses.save_address') }}" class="inline-form">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <input type="hidden" name="id" value="{{ addr.id }}">
              <input type="hidden" name="is_default" value="1">
              <button class="btn btn--secondary btn--sm" type="submit">Set Default</button>
            </form>
            <form method="post" action="{{ url_for('customer_addresses.delete_address', addr_id=addr.id) }}" class="inline-form" data-confirm="Delete this address?">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn--danger btn--sm" type="submit">Delete</button>
            </form>
          </div>"""

replacement = """          <div class="address-card__actions">
            <button type="button" class="btn btn--white btn--sm" onclick="try { document.querySelector('input[name=recipient_name]').value='{{ addr.recipient_name|e }}'; document.querySelector('input[name=phone]').value='{{ addr.phone or '' }}'; document.querySelector('input[name=address_line1]').value='{{ addr.address_line1|e }}'; document.querySelector('input[name=label]').value='{{ addr.label or '' }}'; } catch(e){}">Edit</button>
            <form method="post" action="{{ url_for('customer_addresses') }}" class="inline-form">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <input type="hidden" name="action" value="set_default">
              <input type="hidden" name="address_id" value="{{ addr.id }}">
              <button class="btn btn--secondary btn--sm" type="submit">Set Default</button>
            </form>
            <form method="post" action="{{ url_for('customer_addresses') }}" class="inline-form" onsubmit="return confirm('Delete this address?');">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="address_id" value="{{ addr.id }}">
              <button class="btn btn--danger btn--sm" type="submit">Delete</button>
            </form>
          </div>"""

# Normalize CRLF vs LF
c_norm = c.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in c_norm:
    c_new = c_norm.replace(target_norm, replacement_norm)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c_new)
    print("UI-01 fixed successfully")
else:
    print("Target not found in addresses.html")
