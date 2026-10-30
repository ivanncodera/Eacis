from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from eacis.models.address import Address
from eacis.extensions import db
from eacis.validation import validate_profile_payload
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
import re

bp = Blueprint('customer_addresses', __name__, url_prefix='/customer/addresses')


@bp.route('/', methods=['GET'])
@login_required
def list_addresses():
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id.desc()).all()
    return render_template('customer/addresses.html', addresses=addresses)


@bp.route('/save', methods=['POST'])
@login_required
def save_address():
    data = request.form
    addr_id = data.get('id')
    if addr_id:
        addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first()
        if not addr:
            flash('Address not found', 'danger')
            return redirect(url_for('customer_addresses.list_addresses'))
    else:
        addr = Address(user_id=current_user.id)
        db.session.add(addr)

    # Server-side validation & normalization
    # derive first/last name from recipient_name if provided
    rname = (data.get('recipient_name') or '').strip()
    first = last = ''
    if rname:
        parts = rname.split(None, 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ''
    if not first:
        first = getattr(current_user, 'first_name', '') or ''
    if not last:
        last = getattr(current_user, 'last_name', '') or ''

    payload = {
        'first_name': first,
        'last_name': last,
        'address_line1': data.get('address_line1') or '',
        'address_line2': data.get('address_line2') or '',
        'barangay': data.get('barangay') or '',
        'city_municipality': data.get('city_municipality') or '',
        'province': data.get('province') or '',
        'region': data.get('region') or '',
        'postal_code': data.get('postal_code') or '',
        'phone': data.get('phone') or '',
    }
    errors, normalized = validate_profile_payload(payload, postal_lookup={})
    if errors:
        # Return JSON errors for AJAX; otherwise flash and redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'errors': errors}), 400
        # flash first error
        flash(next(iter(errors.values())), 'danger')
        return redirect(url_for('customer_addresses.list_addresses'))

    addr.recipient_name = data.get('recipient_name') or current_user.computed_full_name or current_user.full_name
    addr.phone = normalized.get('phone')
    addr.postal_code = normalized.get('postal_code')
    addr.address_line1 = normalized.get('address_line1') or ''
    addr.house_number = data.get('house_number')
    addr.landmark = data.get('landmark')
    addr.is_pickup = True if data.get('is_pickup') in ('1', 'true', 'on') else False
    addr.is_return = True if data.get('is_return') in ('1', 'true', 'on') else False
    addr.address_line2 = normalized.get('address_line2')
    addr.barangay = normalized.get('barangay')
    addr.city_municipality = normalized.get('city_municipality')
    addr.province = normalized.get('province')
    addr.region = normalized.get('region')
    addr.label = data.get('label')
    # optional lat/lng
    try:
        lat = data.get('lat')
        lng = data.get('lng')
        if lat:
            addr.lat = float(lat)
        if lng:
            addr.lng = float(lng)
    except Exception:
        pass

    is_default = True if data.get('is_default') in ('1', 'true', 'on') else False
    if is_default:
        # unset other defaults
        Address.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        addr.is_default = True

    db.session.commit()
    # respond with JSON for AJAX callers, else redirect to list view
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'status': 'ok', 'id': addr.id})
    flash('Address saved', 'success')
    return redirect(url_for('customer_addresses.list_addresses'))


@bp.route('/delete/<int:addr_id>', methods=['POST'])
@login_required
def delete_address(addr_id):
    addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first_or_404()
    db.session.delete(addr)
    db.session.commit()
    flash('Address deleted', 'success')
    return redirect(url_for('customer_addresses.list_addresses'))


@bp.route('/api', methods=['GET'])
@login_required
def api_addresses():
    try:
        addrs = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()
    except OperationalError as oe:
        msg = str(oe)
        # Detect missing-column error and attempt to add known missing columns
        m = re.search(r"Unknown column '([^']+)' in 'field list'", msg)
        if m:
            col_full = m.group(1)  # e.g. addresses.house_number or house_number
            # extract column name after dot if present
            col = col_full.split('.')[-1]
            # mapping of columns we can auto-add and their SQL definitions
            col_map = {
                'house_number': 'VARCHAR(255) NULL',
                'landmark': 'TEXT NULL',
                'is_pickup': 'TINYINT(1) NOT NULL DEFAULT 0',
                'is_return': 'TINYINT(1) NOT NULL DEFAULT 0',
            }
            if col in col_map:
                try:
                    sql = f"ALTER TABLE addresses ADD COLUMN {col} {col_map[col]};"
                    db.session.execute(text(sql))
                    db.session.commit()
                    # retry the query once
                    addrs = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'error': 'Database migration failed', 'detail': str(e)}), 500
            else:
                return jsonify({'error': 'Missing column', 'detail': col}), 500
        else:
            return jsonify({'error': 'Database error', 'detail': msg}), 500
    out = []
    for a in addrs:
        out.append({
            'id': a.id,
            'recipient_name': a.recipient_name,
            'phone': a.phone,
            'label': a.label,
            'house_number': getattr(a, 'house_number', None),
            'landmark': getattr(a, 'landmark', None),
            'is_pickup': bool(getattr(a, 'is_pickup', False)),
            'is_return': bool(getattr(a, 'is_return', False)),
            'is_default': bool(a.is_default),
            'postal_code': a.postal_code,
            'address_line1': a.address_line1,
            'address_line2': a.address_line2,
            'barangay': a.barangay,
            'city_municipality': a.city_municipality,
            'province': a.province,
            'region': a.region,
            'lat': getattr(a, 'lat', None),
            'lng': getattr(a, 'lng', None),
        })
    return jsonify(out)
