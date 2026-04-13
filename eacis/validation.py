import re


NAME_PATTERN = re.compile(r"^[a-zA-Z\s'\-\.]+$")
EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
POSTAL_PATTERN = re.compile(r'^\d{4}$')
PHONE_PATTERN = re.compile(r'^09\d{9}$')


def split_name(full_name):
    tokens = [token for token in (full_name or '').strip().split(' ') if token]
    if not tokens:
        return '', '', '', ''
    if len(tokens) == 1:
        return tokens[0], '', '', ''
    if len(tokens) == 2:
        return tokens[0], '', tokens[1], ''
    return tokens[0], ' '.join(tokens[1:-1]), tokens[-1], ''


def join_name(first_name='', middle_name='', last_name='', suffix=''):
    parts = [first_name, middle_name, last_name, suffix]
    return ' '.join([str(part).strip() for part in parts if part and str(part).strip()])


def normalize_phone(raw_phone):
    value = (raw_phone or '').strip().replace(' ', '').replace('-', '')
    if value.startswith('+63') and len(value) == 13 and value[3:].isdigit() and value[3] == '9':
        return '0' + value[3:]
    if value.startswith('63') and len(value) == 12 and value[2:].isdigit() and value[2] == '9':
        return '0' + value[2:]
    if len(value) == 10 and value.isdigit() and value.startswith('9'):
        return '0' + value
    return value


def validate_phone(raw_phone, required=False):
    value = normalize_phone(raw_phone)
    if required and not value:
        return value, 'Phone number is required.'
    if value and not PHONE_PATTERN.match(value):
        return value, 'Enter a valid Philippine mobile number (e.g. 09171234567).'
    return value, None


def validate_postal_code(raw_postal):
    value = (raw_postal or '').strip()
    if value and not POSTAL_PATTERN.match(value):
        return value, 'Postal code must be a 4-digit PH code.'
    return value, None


def validate_registration_payload(payload, role, postal_lookup, email_exists):
    errors = {}

    first_name = (payload.get('first_name') or '').strip()
    middle_name = (payload.get('middle_name') or '').strip()
    last_name = (payload.get('last_name') or '').strip()
    suffix = (payload.get('suffix') or '').strip()

    address_line1 = (payload.get('address_line1') or '').strip()
    barangay = (payload.get('barangay') or '').strip()
    city_municipality = (payload.get('city_municipality') or '').strip()
    province = (payload.get('province') or '').strip()
    postal_code = (payload.get('postal_code') or '').strip()

    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    confirm = payload.get('confirm_password') or ''
    agree = payload.get('agree')

    # Identity Validation
    if not first_name:
        errors['first_name'] = 'First name is required.'
    elif not NAME_PATTERN.match(first_name):
        errors['first_name'] = 'First name contains invalid characters.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'
    elif not NAME_PATTERN.match(last_name):
        errors['last_name'] = 'Last name contains invalid characters.'

    normalized_full_name = join_name(first_name, middle_name, last_name, suffix)

    # Contact/Email Validation
    if not email:
        errors['email'] = 'Email address is required.'
    elif not EMAIL_PATTERN.match(email):
        errors['email'] = 'Please enter a valid email address.'
    elif email_exists(email):
        errors['email'] = 'An account with this email already exists.'

    phone, phone_error = validate_phone(payload.get('phone'), required=True)
    if phone_error:
        errors['phone'] = phone_error

    # Security Validation
    if len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters long.'
    else:
        checks = {
            r'[A-Z]': 'at least one uppercase letter',
            r'[a-z]': 'at least one lowercase letter',
            r'\d': 'at least one number',
            r'[^A-Za-z0-9]': 'at least one special character'
        }
        missing = [desc for reg, desc in checks.items() if not re.search(reg, password)]
        if missing:
            errors['password'] = f"Password must contain {', '.join(missing)}."

    if password != confirm:
        errors['confirm_password'] = 'Passwords do not match.'

    if not agree:
        errors['agree'] = 'You must accept the terms to continue.'

    # Role-Specific Validation (Seller)
    business_name = ''
    if role == 'seller':
        business_name = (payload.get('business_name') or '').strip()
        if not business_name or len(business_name) < 3:
            errors['business_name'] = 'A valid business name (min 3 chars) is required.'

    # Location Suggestion Logic (Partial)
    suggested_postal = postal_lookup.get(city_municipality.lower()) if city_municipality else None
    postal_val, postal_err = validate_postal_code(postal_code)
    if postal_err:
        errors['postal_code'] = postal_err
    if not postal_val and suggested_postal:
        postal_val = suggested_postal

    normalized = {
        'first_name': first_name,
        'middle_name': middle_name,
        'last_name': last_name,
        'suffix': suffix,
        'full_name': normalized_full_name,
        'address_line1': address_line1,
        'address_line2': (payload.get('address_line2') or '').strip(),
        'barangay': barangay,
        'city_municipality': city_municipality,
        'province': province,
        'region': (payload.get('region') or '').strip(),
        'postal_code': postal_val,
        'email': email,
        'phone': phone,
        'password': password,
        'business_name': business_name,
        'role': role,
        'agree': bool(agree),
    }
    return errors, normalized


def validate_profile_payload(payload, postal_lookup):
    errors = {}
    first_name = (payload.get('first_name') or '').strip()
    middle_name = (payload.get('middle_name') or '').strip()
    last_name = (payload.get('last_name') or '').strip()
    suffix = (payload.get('suffix') or '').strip()

    address_line1 = (payload.get('address_line1') or '').strip()
    address_line2 = (payload.get('address_line2') or '').strip()
    barangay = (payload.get('barangay') or '').strip()
    city_municipality = (payload.get('city_municipality') or '').strip()
    province = (payload.get('province') or '').strip()
    region = (payload.get('region') or '').strip()
    postal_code = (payload.get('postal_code') or '').strip()

    if not first_name or not last_name:
        errors['full_name'] = 'First name and last name are required.'

    phone, phone_error = validate_phone(payload.get('phone'))
    if phone_error:
        errors['phone'] = phone_error

    postal_code, postal_error = validate_postal_code(postal_code)
    if postal_error:
        errors['postal_code'] = postal_error

    suggested_postal = postal_lookup.get(city_municipality.lower()) if city_municipality else None
    if not postal_code and suggested_postal:
        postal_code = suggested_postal

    normalized = {
        'first_name': first_name,
        'middle_name': middle_name,
        'last_name': last_name,
        'suffix': suffix,
        'full_name': join_name(first_name, middle_name, last_name, suffix),
        'phone': phone,
        'address_line1': address_line1,
        'address_line2': address_line2,
        'barangay': barangay,
        'city_municipality': city_municipality,
        'province': province,
        'region': region,
        'postal_code': postal_code,
    }
    return errors, normalized


def validate_checkout_payload(payload):
    errors = {}
    recipient_name = (payload.get('recipient_name') or '').strip()
    address_line1 = (payload.get('address_line1') or payload.get('address') or '').strip()
    postal_code = (payload.get('postal_code') or '').strip()

    if not recipient_name:
        errors['recipient_name'] = 'Recipient name is required.'
    if not address_line1:
        errors['address_line1'] = 'Delivery address is required.'

    phone, phone_error = validate_phone(payload.get('phone'), required=True)
    if phone_error:
        errors['phone'] = phone_error

    postal_code, postal_error = validate_postal_code(postal_code)
    if postal_error:
        errors['postal_code'] = postal_error

    payment_method = (payload.get('payment') or 'full_pay').strip()
    if payment_method not in ('full_pay', 'installment'):
        payment_method = 'full_pay'

    plan_months = 12
    try:
        posted_plan = int(payload.get('plan') or 12)
        if posted_plan in (6, 12, 24):
            plan_months = posted_plan
    except Exception:
        plan_months = 12

    normalized = {
        'recipient_name': recipient_name,
        'address_line1': address_line1,
        'address_line2': (payload.get('address_line2') or '').strip(),
        'barangay': (payload.get('barangay') or '').strip(),
        'city_municipality': (payload.get('city_municipality') or payload.get('city') or '').strip(),
        'province': (payload.get('province') or '').strip(),
        'region': (payload.get('region') or '').strip(),
        'postal_code': postal_code,
        'phone': phone,
        'country': 'Philippines',
        'payment_method': payment_method,
        'plan_months': plan_months,
    }
    return errors, normalized


def validate_return_payload(payload):
    order_ref = (payload.get('order_ref') or '').strip()
    reason = (payload.get('reason') or '').strip()
    description = (payload.get('description') or '').strip()
    errors = {}

    if not order_ref:
        errors['order_ref'] = 'Order reference is required.'
    if not reason:
        errors['reason'] = 'Reason is required.'
    if not description:
        errors['description'] = 'Description is required.'

    normalized = {
        'order_ref': order_ref,
        'reason': reason,
        'description': description,
    }
    return errors, normalized


def validate_seller_return_update_payload(payload):
    action = (payload.get('action') or '').strip()
    notes = (payload.get('seller_notes') or '').strip()
    valid_actions = {'approve', 'deny', 'refund'}
    errors = {}
    if action not in valid_actions:
        errors['action'] = 'Invalid return action.'
    return errors, {'action': action, 'seller_notes': notes}


def validate_seller_profile_payload(payload, postal_lookup):
    errors = {}
    business_name = (payload.get('business_name') or '').strip()
    full_name = (payload.get('full_name') or '').strip()
    phone, phone_error = validate_phone(payload.get('phone'))

    address_line1 = (payload.get('address_line1') or '').strip()
    address_line2 = (payload.get('address_line2') or '').strip()
    barangay = (payload.get('barangay') or '').strip()
    city_municipality = (payload.get('city_municipality') or '').strip()
    province = (payload.get('province') or '').strip()
    region = (payload.get('region') or '').strip()
    postal_code = (payload.get('postal_code') or '').strip()

    if len(business_name) < 2:
        errors['business_name'] = 'Business name is required.'
    if len(full_name) < 2:
        errors['full_name'] = 'Owner name is required.'
    if phone_error:
        errors['phone'] = phone_error

    postal_code, postal_error = validate_postal_code(postal_code)
    if postal_error:
        errors['postal_code'] = postal_error

    suggested_postal = postal_lookup.get(city_municipality.lower()) if city_municipality else None
    if not postal_code and suggested_postal:
        postal_code = suggested_postal

    normalized = {
        'business_name': business_name,
        'full_name': full_name,
        'phone': phone,
        'address_line1': address_line1,
        'address_line2': address_line2,
        'barangay': barangay,
        'city_municipality': city_municipality,
        'province': province,
        'region': region,
        'postal_code': postal_code,
    }
    return errors, normalized


def validate_inquiry_create_payload(payload, customer_exists, order_exists):
    errors = {}
    subject = (payload.get('subject') or '').strip()
    description = (payload.get('description') or '').strip()
    priority = (payload.get('priority') or 'medium').strip()
    customer_email = (payload.get('customer_email') or '').strip().lower()
    order_ref = (payload.get('order_ref') or '').strip()

    if not subject:
        errors['subject'] = 'Subject is required.'
    if not description:
        errors['description'] = 'Description is required.'
    if not EMAIL_PATTERN.match(customer_email):
        errors['customer_email'] = 'Enter a valid customer email.'
    elif not customer_exists(customer_email):
        errors['customer_email'] = 'Customer email was not found.'
    if order_ref and not order_exists(order_ref):
        errors['order_ref'] = 'Order reference was not found.'
    if priority not in ('low', 'medium', 'high', 'urgent'):
        priority = 'medium'

    normalized = {
        'subject': subject,
        'description': description,
        'priority': priority,
        'customer_email': customer_email,
        'order_ref': order_ref,
    }
    return errors, normalized


def validate_inquiry_update_payload(payload):
    errors = {}
    next_status = (payload.get('status') or '').strip()
    note = (payload.get('description') or '').strip()
    if next_status not in ('open', 'in_progress', 'resolved', 'closed'):
        errors['status'] = 'Invalid status selected.'
    if not note:
        errors['description'] = 'Description is required.'
    return errors, {'status': next_status, 'description': note}


def validate_seller_security_payload(payload, check_current_password):
    errors = {}
    current_password = payload.get('current_password') or ''
    new_password = payload.get('new_password') or ''
    confirm_password = payload.get('confirm_password') or ''

    if not check_current_password(current_password):
        errors['current_password'] = 'Current password is incorrect.'
    if len(new_password) < 8:
        errors['new_password'] = 'New password must be at least 8 characters.'
    if new_password != confirm_password:
        errors['confirm_password'] = 'New password and confirmation do not match.'

    normalized = {
        'current_password': current_password,
        'new_password': new_password,
        'confirm_password': confirm_password,
    }
    return errors, normalized


def validate_cart_quantity_payload(payload, max_stock=None):
    errors = {}
    raw_qty = payload.get('qty')

    try:
        qty = int(raw_qty)
    except (TypeError, ValueError):
        qty = 1

    if qty < 1:
        errors['qty'] = 'Quantity must be at least 1.'
        qty = 1

    if max_stock is not None:
        try:
            stock_limit = int(max_stock)
        except (TypeError, ValueError):
            stock_limit = 0

        if stock_limit < 1:
            errors['qty'] = 'This product is out of stock.'
            qty = 1
        elif qty > stock_limit:
            errors['qty'] = f'Only {stock_limit} item(s) available in stock.'
            qty = stock_limit

    return errors, {'qty': qty}


def validate_seller_product_payload(payload):
    errors = {}

    name = (payload.get('name') or '').strip()
    category = (payload.get('category') or '').strip()
    description = (payload.get('description') or '').strip()
    price_raw = payload.get('price')
    stock_raw = payload.get('stock')
    warranty_raw = payload.get('warranty_months')
    is_active = (payload.get('is_active') or '1').strip() == '1'
    installment_enabled = bool(payload.get('installment_enabled'))

    try:
        price = float(price_raw or 0)
    except (TypeError, ValueError):
        price = -1

    try:
        stock = int(stock_raw or 0)
    except (TypeError, ValueError):
        stock = -1

    try:
        warranty_months = int(warranty_raw or 0)
    except (TypeError, ValueError):
        warranty_months = 0

    if not name or len(name) < 3:
        errors['name'] = 'Product name must be at least 3 characters.'
    if not category:
        errors['category'] = 'Category is required.'
    if price < 0:
        errors['price'] = 'Price must be a valid non-negative number.'
    if stock < 0:
        errors['stock'] = 'Stock must be a valid non-negative integer.'

    normalized = {
        'name': name,
        'category': category,
        'description': description,
        'price_raw': price_raw,
        'stock_raw': stock_raw,
        'warranty_raw': warranty_raw,
        'price': price,
        'stock': stock,
        'warranty_months': max(warranty_months, 0),
        'is_active': is_active,
        'installment_enabled': installment_enabled,
    }
    return errors, normalized
