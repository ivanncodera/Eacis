from flask import Flask, render_template
from flask import redirect, url_for, request, jsonify
from flask import flash, session
import time
import csv
import io
import os
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
# If run directly as a script on terminal bro (``python eacis/app.py``), to ensure package imports work
if __name__ == '__main__' and __package__ is None:
    import sys, pathlib
    pkg_root = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(pkg_root.parent))
    __package__ = pkg_root.name
try:
    from .config import Config
except Exception:
    # allow running the module as a script (no package)
    from config import Config
try:
    from .extensions import db, csrf, login_manager, migrate
except Exception:
    try:
        from extensions import db, csrf, login_manager, migrate
    except Exception:
        from eacis.extensions import db, csrf, login_manager, migrate
try:
    from .validation import (
        join_name,
        validate_registration_payload,
        validate_profile_payload,
        validate_checkout_payload,
        validate_return_payload,
        validate_seller_return_update_payload,
        validate_seller_profile_payload,
        validate_inquiry_create_payload,
        validate_inquiry_update_payload,
        validate_seller_security_payload,
        validate_cart_quantity_payload,
        validate_seller_product_payload,
    )
except Exception:
    from validation import (
        join_name,
        validate_registration_payload,
        validate_profile_payload,
        validate_checkout_payload,
        validate_return_payload,
        validate_seller_return_update_payload,
        validate_seller_profile_payload,
        validate_inquiry_create_payload,
        validate_inquiry_update_payload,
        validate_seller_security_payload,
        validate_cart_quantity_payload,
        validate_seller_product_payload,
    )

 
def create_app(config_class=Config):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)


    db.init_app(app)
    # Ensure SQLAlchemy registers an engine bound to this app instance.
    # Some environments lazily create the engine without an app, which
    # leaves it keyed under None; proactively request the engine so it
    # is registered to the current app object.
    try:
        if hasattr(db, 'get_engine'):
            db.get_engine(app)
        else:
            # older/newer versions may expose `engine` property lazily
            _ = getattr(db, 'engine', None)
    except Exception:
        pass
    # If an engine was created earlier without an app (keyed by None),
    # associate it with this app instance so session.get_bind() finds it.
    try:
        engines = getattr(db, 'engines', None)
        if isinstance(engines, dict) and None in engines:
            engines[app] = engines.pop(None)
    except Exception:
        pass
    csrf.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Simple in-memory login guardrails for abuse control.
    # Structure: {(scope, identity): {'count': int, 'locked_until': float, 'window_start': float}}
    app._login_attempts = {}

    # Configure Flask-Login
    login_manager.login_view = 'auth_login'

    # import here to avoid circular imports during module import time
    try:
        from .models.user import User
    except Exception:
        from models.user import User

    # Create simple dev users if DB is empty (development convenience)
    def ensure_dev_users():
        try:
            with app.app_context():
                db.create_all()
                try:
                    from .models.voucher import Voucher
                except Exception:
                    try:
                        from models.voucher import Voucher
                    except Exception:
                        Voucher = None
                demo_users = [
                    ('customer@example.com', 'customer', 'Dev Customer'),
                    ('seller@example.com', 'seller', 'Dev Seller'),
                    ('admin@example.com', 'admin', 'Dev Admin'),
                ]
                changed = False
                for email, role, full_name in demo_users:
                    user = User.query.filter_by(email=email).first()
                    if user is None:
                        user = User(email=email, role=role, full_name=full_name)
                        user.set_password('password')
                        db.session.add(user)
                        changed = True

                if Voucher is not None:
                    sample_vouchers = [
                        {
                            'code': 'WELCOME10',
                            'voucher_ref': 'VCH-WELCOME10',
                            'discount_type': 'percent',
                            'discount_value': 10,
                            'min_order_amount': 1000,
                            'max_uses': 1000,
                            'per_user_limit': 2,
                            'is_active': True,
                            'combinable': False,
                        },
                        {
                            'code': 'LESS500',
                            'voucher_ref': 'VCH-LESS500',
                            'discount_type': 'fixed',
                            'discount_value': 500,
                            'min_order_amount': 5000,
                            'max_uses': 500,
                            'per_user_limit': 1,
                            'is_active': True,
                            'combinable': False,
                        },
                    ]
                    for item in sample_vouchers:
                        if not Voucher.query.filter_by(code=item['code']).first():
                            db.session.add(Voucher(**item))
                            changed = True
                if changed:
                    db.session.commit()
        except Exception:
            # if migrations or DB unavailable, skip silently
            pass
    # Only run dev seeds when explicitly enabled in configuration
    try:
        if app.config.get('USE_DEV_SEEDS'):
            ensure_dev_users()
    except Exception:
        # if config unreadable or missing, skip seeding
        pass

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    postal_lookup = {
        'quezon city': '1100',
        'manila': '1000',
        'makati': '1226',
        'pasig': '1600',
        'taguig': '1630',
        'cebu city': '6000',
        'davao city': '8000',
    }

    def ensure_invoice_for_order(order):
        try:
            from .models.invoice import Invoice
            from .models.order import OrderItem
            from .models.product import Product
        except Exception:
            from models.invoice import Invoice
            from models.order import OrderItem
            from models.product import Product

        if not order or not getattr(order, 'id', None):
            return None

        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        if not order_items:
            return None

        seller_totals = {}
        for item in order_items:
            product = Product.query.get(item.product_id) if item and item.product_id else None
            seller_id = getattr(product, 'seller_id', None)
            if not seller_id:
                continue
            line_total = float(item.subtotal or ((item.unit_price or 0) * (item.quantity or 0)) or 0)
            seller_totals[seller_id] = float(seller_totals.get(seller_id, 0.0)) + line_total

        if not seller_totals:
            return None

        created = []
        grand_total = float(order.total or 0)
        safe_grand_total = grand_total if grand_total > 0 else float(sum(seller_totals.values()))
        discount_ratio = (float(order.discount or 0) / safe_grand_total) if safe_grand_total > 0 else 0.0
        tax_ratio = (float(order.tax or 0) / safe_grand_total) if safe_grand_total > 0 else 0.0
        shipping_ratio = (float(order.shipping_fee or 0) / safe_grand_total) if safe_grand_total > 0 else 0.0

        for seller_id, subtotal in seller_totals.items():
            if Invoice.query.filter_by(order_id=order.id, seller_id=seller_id).first():
                continue

            discount_total = round(subtotal * discount_ratio, 2)
            tax_total = round(subtotal * tax_ratio, 2)
            shipping_total = round(subtotal * shipping_ratio, 2)
            grand_total_per_seller = round(subtotal - discount_total + tax_total + shipping_total, 2)

            invoice = Invoice(
                invoice_ref=f"INV-{order.order_ref}-{seller_id}",
                order_id=order.id,
                customer_id=order.customer_id,
                seller_id=seller_id,
                subtotal=round(subtotal, 2),
                discount_total=discount_total,
                tax_total=tax_total,
                shipping_total=shipping_total,
                grand_total=grand_total_per_seller,
                status='paid' if order.status == 'paid' else 'issued',
                issued_at=datetime.utcnow(),
                due_at=datetime.utcnow() + timedelta(days=7),
            )
            db.session.add(invoice)
            created.append(invoice)
        return created

    def calculate_refund_amount(order, seller_id=None):
        try:
            from .models.order import OrderItem
            from .models.product import Product
        except Exception:
            from models.order import OrderItem
            from models.product import Product

        if not order:
            return 0.0

        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        if not order_items:
            return round(float(order.total or order.subtotal or 0), 2)

        full_items_subtotal = 0.0
        scoped_items_subtotal = 0.0

        for item in order_items:
            line_total = float(item.subtotal or ((item.unit_price or 0) * (item.quantity or 0)) or 0)
            full_items_subtotal += line_total

            if seller_id is None:
                scoped_items_subtotal += line_total
            else:
                product = Product.query.get(item.product_id) if item.product_id else None
                if product and int(product.seller_id or 0) == int(seller_id):
                    scoped_items_subtotal += line_total

        if scoped_items_subtotal <= 0:
            return 0.0

        if seller_id is None:
            return round(float(order.total or full_items_subtotal or 0), 2)

        order_subtotal = float(order.subtotal or full_items_subtotal or 0)
        order_total = float(order.total or full_items_subtotal or 0)
        if order_subtotal <= 0:
            return round(scoped_items_subtotal, 2)

        ratio = scoped_items_subtotal / order_subtotal
        ratio = min(max(ratio, 0.0), 1.0)
        return round(order_total * ratio, 2)

    def validate_voucher_for_cart(voucher_code, cart_items, subtotal, customer_id, VoucherModel, OrderModel):
        normalized_code = (voucher_code or '').strip().upper()
        if not normalized_code:
            return None, '', 0.0, None

        voucher = VoucherModel.query.filter(VoucherModel.code.ilike(normalized_code)).first()
        if not voucher:
            return None, '', 0.0, 'Voucher code not found.'
        if not voucher.is_valid():
            return None, '', 0.0, 'Voucher is not active or already expired.'

        eligible_subtotal = float(subtotal)
        if voucher.seller_id:
            eligible_subtotal = sum(
                float(line.get('line_total') or 0)
                for line in (cart_items or [])
                if getattr(line.get('product'), 'seller_id', None) == voucher.seller_id
            )
            if eligible_subtotal <= 0:
                return None, '', 0.0, 'Voucher is only valid for specific seller products in your cart.'

        if eligible_subtotal < float(voucher.min_order_amount or 0):
            return None, '', 0.0, f'Voucher requires minimum order of PHP {float(voucher.min_order_amount or 0):.2f}.'
        if voucher.max_uses is not None and int(voucher.uses_count or 0) >= int(voucher.max_uses):
            return None, '', 0.0, 'Voucher has reached maximum redemptions.'

        used_count = OrderModel.query.filter_by(customer_id=customer_id, voucher_id=voucher.id).count()
        if voucher.per_user_limit is not None and used_count >= int(voucher.per_user_limit):
            return None, '', 0.0, 'You have reached your usage limit for this voucher.'

        if (voucher.discount_type or '').strip() == 'percent':
            discount = eligible_subtotal * (float(voucher.discount_value or 0) / 100.0)
        else:
            discount = float(voucher.discount_value or 0)
        discount = max(min(discount, eligible_subtotal), 0.0)
        return voucher, voucher.code, float(discount), None

    def money(value):
        try:
            return round(float(value or 0), 2)
        except Exception:
            return 0.0

    # Session API for frontend to detect role and auth status
    @app.route('/api/session')
    def api_session():
        from flask_login import current_user
        if current_user and getattr(current_user, 'is_authenticated', False):
            return jsonify({
                'authenticated': True,
                'role': getattr(current_user, 'role', 'customer'),
                'id': current_user.get_id()
            })
        return jsonify({'authenticated': False, 'role': None})

    @app.route('/api/postal/suggest')
    def postal_suggest():
        city = (request.args.get('city') or '').strip().lower()
        return jsonify({'city': city, 'postal_code': postal_lookup.get(city)})

    @app.route('/api/cart/summary')
    def api_cart_summary():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return jsonify({'items': [], 'count': 0, 'subtotal': 0.0})

        try:
            from .models.cart import Cart
            from .models.product import Product
            from .models.voucher import Voucher
            from .models.order import Order
        except Exception:
            from models.cart import Cart
            from models.product import Product
            from models.voucher import Voucher
            from models.order import Order

        cart = Cart.query.filter_by(user_id=current_user.id).first()
        raw_items = list(getattr(cart, 'items', None) or [])

        items = []
        subtotal = 0.0
        count = 0
        for entry in raw_items:
            product = Product.query.get(entry.get('product_id'))
            if not product:
                continue
            qty = max(int(entry.get('qty') or 1), 1)
            unit_price = float(product.price or 0)
            line_total = unit_price * qty
            subtotal += line_total
            count += qty
            items.append({
                'product_ref': product.product_ref,
                'name': product.name,
                'qty': qty,
                'unit_price': unit_price,
                'line_total': line_total,
                'image_url': product.image_url or '/static/assets/products/refrigerator.webp',
            })

        return jsonify({'items': items, 'count': count, 'subtotal': subtotal})

    # Global route guard for portal prefixes
    @app.before_request
    def enforce_portal_guards():
        from flask_login import current_user
        path = request.path
        # allow static/api/auth/public pages. Keep '/' exact to avoid bypassing all guards.
        allowed_prefixes = ('/static/', '/api/', '/auth', '/landing', '/shop', '/product', '/about', '/contact', '/terms', '/privacy')
        if path == '/' or any(path.startswith(p) for p in allowed_prefixes):
            return None
        # customer portal
        if path.startswith('/customer'):
            if not (current_user and getattr(current_user, 'is_authenticated', False)):
                return redirect(url_for('auth_login', next=request.path))
            if getattr(current_user, 'role', None) != 'customer':
                # redirect to their portal home
                role = getattr(current_user, 'role', None)
                if role == 'seller':
                    return redirect(url_for('seller_dashboard'))
                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('auth_login', next=request.path))
        # seller portal
        if path.startswith('/seller'):
            if not (current_user and getattr(current_user, 'is_authenticated', False)):
                return redirect(url_for('auth_login', next=request.path))
            if getattr(current_user, 'role', None) != 'seller':
                role = getattr(current_user, 'role', None)
                if role == 'customer':
                    return redirect(url_for('shop'))
                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('auth_login', next=request.path))
            verification_status = (getattr(current_user, 'seller_verification_status', '') or '').lower()
            if verification_status in ('pending', 'rejected'):
                allowed_prefixes_for_unverified = (
                    '/seller/dashboard',
                    '/seller/profile',
                    '/seller/security',
                )
                if not any(path.startswith(prefix) for prefix in allowed_prefixes_for_unverified):
                    flash('Your seller account is under verification. Some seller features are temporarily restricted.', 'warning')
                    return redirect(url_for('seller_dashboard'))
        # admin portal
        if path.startswith('/admin'):
            if not (current_user and getattr(current_user, 'is_authenticated', False)):
                return redirect(url_for('auth_login', next=request.path))
            if getattr(current_user, 'role', None) != 'admin':
                role = getattr(current_user, 'role', None)
                if role == 'customer':
                    return redirect(url_for('shop'))
                if role == 'seller':
                    return redirect(url_for('seller_dashboard'))
                return redirect(url_for('auth_login', next=request.path))
        return None

    # Blueprints will be registered here later

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500

    def build_landing_context():
        try:
            from .models.product import Product
            from .models.user import User
        except Exception:
            from models.product import Product
            from models.user import User

        featured = (
            Product.query
            .filter_by(is_active=True)
            .order_by(Product.created_at.desc())
            .limit(8)
            .all()
        )

        def _product_card_dict(product):
            cp = getattr(product, 'compare_price', None)
            return {
                'ref': product.product_ref,
                'product_ref': product.product_ref,
                'name': product.name,
                'category': product.category,
                'price': float(product.price or 0),
                'stock': int(product.stock or 0),
                'image_url': product.image_url or '/static/assets/products/refrigerator.webp',
                'installment_enabled': bool(getattr(product, 'installment_enabled', False)),
                'comparePrice': float(cp) if cp is not None else None,
            }

        featured_products = [_product_card_dict(p) for p in featured]

        hero = None
        if featured:
            p = featured[0]
            specs = p.specs if isinstance(getattr(p, 'specs', None), dict) else {}
            hero = {
                'name': p.name,
                'category': (p.category or '').strip(),
                'product_ref': p.product_ref,
                'image_url': p.image_url or '/static/assets/products/refrigerator.webp',
                'warranty_months': int(p.warranty_months or 0),
                'installment_enabled': bool(p.installment_enabled),
                'energy_rating': (specs.get('energy_rating') or specs.get('energy') or '').strip() or None,
                'price': float(p.price or 0),
            }

        category_rows = db.session.query(Product.category).filter(
            Product.is_active.is_(True),
            Product.category.isnot(None),
            Product.category != '',
        ).distinct().order_by(Product.category.asc()).all()
        shop_categories = [r[0] for r in category_rows if r[0]]

        spotlight_rows = (
            Product.query.filter(
                Product.is_active.is_(True),
                Product.compare_price.isnot(None),
                Product.price.isnot(None),
                Product.compare_price > Product.price,
            )
            .order_by(Product.created_at.desc())
            .limit(6)
            .all()
        )
        spotlight_deals = []
        for p in spotlight_rows:
            try:
                save_amt = float(p.compare_price or 0) - float(p.price or 0)
            except (TypeError, ValueError):
                save_amt = 0.0
            spotlight_deals.append({
                'name': p.name,
                'product_ref': p.product_ref,
                'save_amount': max(0.0, save_amt),
                'price': float(p.price or 0),
                'compare_price': float(p.compare_price or 0),
            })

        active_products = Product.query.filter_by(is_active=True).count()
        seller_count = User.query.filter_by(role='seller').count()

        return {
            'featured_products': featured_products,
            'featured_count': len(featured_products),
            'active_count': active_products,
            'shop_categories': shop_categories,
            'hero': hero,
            'spotlight_deals': spotlight_deals,
            'platform_stats': {
                'active_products': active_products,
                'sellers': seller_count,
                'categories': len(shop_categories),
                'return_window_days': int(Config.RETURN_WINDOW_DAYS),
            },
        }

    def static_page_payload(page_key, title):
        pages = {
            'about': {
                'intro': 'E-ACIS is a marketplace platform focused on trusted appliance commerce with role-based experiences for customers, sellers, and administrators.',
                'principles': [
                    {'title': 'Utility-First Design', 'description': 'Fast, clear navigation across shopping, seller operations, and administration.'},
                    {'title': 'Secure Transactions', 'description': 'Role guards, CSRF protection, and secure authentication for every state-changing workflow.'},
                    {'title': 'Data-Driven Operations', 'description': 'Insights and workflows are sourced from transactional records instead of hardcoded business entries.'},
                ],
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d'),
                'doc_ref': 'ACIS-ABOUT-2026',
            },
            'contact': {
                'intro': 'Reach the E-ACIS team through verified support channels for account assistance, technical issues, and marketplace concerns.',
                'principles': [
                    {'title': 'Support Hours', 'description': 'Customer support is available daily with prioritized handling for order-impacting issues.'},
                    {'title': 'Escalation Path', 'description': 'Seller and customer concerns are routed through inquiry and return workflows for auditability.'},
                    {'title': 'Response Standards', 'description': 'Critical reports are acknowledged first, then resolved through tracked ticket updates.'},
                ],
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d'),
                'doc_ref': 'ACIS-CONTACT-2026',
            },
            'terms': {
                'intro': 'These terms define acceptable use, transaction behavior, and account responsibilities across customer, seller, and admin portals.',
                'principles': [
                    {'title': 'Account Responsibility', 'description': 'Users are responsible for maintaining accurate account and business information.'},
                    {'title': 'Marketplace Conduct', 'description': 'Orders, returns, and inquiries must follow platform workflows and role restrictions.'},
                    {'title': 'Policy Enforcement', 'description': 'Violations may trigger account restrictions, suspension, or further administrative review.'},
                ],
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d'),
                'doc_ref': 'ACIS-TERMS-2026',
            },
            'privacy': {
                'intro': 'E-ACIS processes account, order, and operational data to deliver platform functionality while protecting user privacy.',
                'principles': [
                    {'title': 'Data Minimization', 'description': 'Only required profile and transaction fields are collected for platform operations.'},
                    {'title': 'Protection Controls', 'description': 'Access is restricted by role and sensitive actions are auditable in administrative logs.'},
                    {'title': 'Retention Practice', 'description': 'Operational records are retained for support, compliance, and service integrity.'},
                ],
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d'),
                'doc_ref': 'ACIS-PRIVACY-2026',
            },
        }

        payload = pages.get(page_key, pages['about']).copy()
        payload['title'] = title
        return payload

    @app.route('/')
    def index():
        return render_template('landing.html', **build_landing_context())

    @app.route('/landing')
    def landing():
        return render_template('landing.html', **build_landing_context())

    @app.route('/auth/login')
    def auth_login():
        def _client_ip():
            forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
            return forwarded or request.remote_addr or 'unknown'

        def _now_ts():
            return time.time()

        def _rate_limit_config():
            return {
                'window_seconds': 900,
                'max_attempts_per_email': 5,
                'max_attempts_per_ip': 20,
                'lockout_seconds': 600,
            }

        def _get_state(key, now_ts):
            state = app._login_attempts.get(key) or {'count': 0, 'locked_until': 0.0, 'window_start': now_ts}
            if now_ts - float(state.get('window_start') or now_ts) > _rate_limit_config()['window_seconds']:
                state = {'count': 0, 'locked_until': 0.0, 'window_start': now_ts}
            app._login_attempts[key] = state
            return state

        def _lock_and_count(key, max_attempts, now_ts):
            state = _get_state(key, now_ts)
            state['count'] = int(state.get('count') or 0) + 1
            if state['count'] >= max_attempts:
                state['locked_until'] = now_ts + _rate_limit_config()['lockout_seconds']
                state['count'] = 0
                state['window_start'] = now_ts
            app._login_attempts[key] = state
            return state

        def _remaining_lock(key, now_ts):
            state = _get_state(key, now_ts)
            locked_until = float(state.get('locked_until') or 0.0)
            if now_ts < locked_until:
                return int(max(locked_until - now_ts, 0))
            return 0

        def _reset_guardrails(email, ip):
            for key in (('email', email), ('ip', ip)):
                app._login_attempts.pop(key, None)

        # GET renders the form; POST handles submission
        if request.method == 'POST':
            try:
                email = request.form.get('email','').strip().lower()
                password = request.form.get('password','')
                remember = bool(request.form.get('remember'))
                client_ip = _client_ip()
                now_ts = _now_ts()

                email_lock_remaining = _remaining_lock(('email', email), now_ts)
                ip_lock_remaining = _remaining_lock(('ip', client_ip), now_ts)
                lock_remaining = max(email_lock_remaining, ip_lock_remaining)

                if lock_remaining > 0:
                    error = f"Account temporarily locked. Try again in {lock_remaining} seconds."
                    return render_template('auth/login.html', error=error)
                user = User.query.filter_by(email=email).first()
                if not user or not user.check_password(password):
                    email_state = _lock_and_count(('email', email), _rate_limit_config()['max_attempts_per_email'], now_ts)
                    ip_state = _lock_and_count(('ip', client_ip), _rate_limit_config()['max_attempts_per_ip'], now_ts)
                    email_locked = now_ts < float(email_state.get('locked_until') or 0)
                    ip_locked = now_ts < float(ip_state.get('locked_until') or 0)

                    if email_locked or ip_locked:
                        error = 'Account temporarily locked. Try again in 600 seconds.'
                    else:
                        error = 'Incorrect email or password. Try again.'
                    return render_template('auth/login.html', error=error)
                
                # success
                from flask_login import login_user
                login_user(user, remember=remember)
                _reset_guardrails(email, client_ip)
                # decide redirect
                nxt = request.args.get('next') or request.form.get('next') or ''
                def safe_redirect_for_role(role, target):
                    if not target or not target.startswith('/'):
                        return None
                    if target.startswith('/admin') and role != 'admin':
                        return None
                    if target.startswith('/seller') and role != 'seller':
                        return None
                    if target.startswith('/customer') and role != 'customer':
                        return None
                    return target
                dest = safe_redirect_for_role(user.role, nxt)
                if not dest:
                    if user.role == 'customer': dest = url_for('shop')
                    elif user.role == 'seller': dest = url_for('seller_dashboard')
                    elif user.role == 'admin': dest = url_for('admin_dashboard')
                    else: dest = url_for('index')
                return redirect(dest)
            except Exception:
                # Keep logs operationally useful while avoiding sensitive payload leakage.
                app.logger.exception('Unhandled login error during authentication flow.')
                raise
        return render_template('auth/login.html')
    # allow POST on the same endpoint
    app.add_url_rule('/auth/login', endpoint='auth_login', view_func=auth_login, methods=['GET','POST'])

    def save_seller_permit(upload_file, prefix):
        if not upload_file or not upload_file.filename:
            return None, 'Missing required permit file.'
        allowed = {'.pdf', '.png', '.jpg', '.jpeg'}
        sanitized = secure_filename(upload_file.filename)
        ext = os.path.splitext(sanitized)[1].lower()
        if ext not in allowed:
            return None, 'Permit files must be PDF, PNG, JPG, or JPEG.'

        # Keep permit files outside /static to avoid public direct access.
        upload_dir = os.path.join(app.instance_path, 'uploads', 'permits')
        os.makedirs(upload_dir, exist_ok=True)
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        filename = f"{prefix}_{ts}_{sanitized}"
        abs_path = os.path.join(upload_dir, filename)
        upload_file.save(abs_path)
        return f"permits/{filename}", None

    @app.route('/auth/register', methods=['GET', 'POST'])
    def auth_register():
        if request.method == 'POST':
            selected_role = (request.form.get('role') or 'customer').strip().lower()
            if selected_role == 'seller':
                return redirect(url_for('auth_register_seller'))
            return redirect(url_for('auth_register_customer'))
        return render_template('auth/register_role_select.html')

    @app.route('/auth/register/customer', methods=['GET', 'POST'])
    def auth_register_customer():
        if request.method == 'POST':
            errors, normalized = validate_registration_payload(
                request.form,
                'customer',
                postal_lookup,
                email_exists=lambda email: User.query.filter_by(email=email).first() is not None,
            )
            if errors:
                return render_template('auth/register_customer.html', errors=errors, form=normalized)
            try:
                new_user = User(
                    email=normalized['email'],
                    role='customer',
                    full_name=normalized['full_name'],
                    first_name=normalized['first_name'] or None,
                    middle_name=normalized['middle_name'] or None,
                    last_name=normalized['last_name'] or None,
                    suffix=normalized['suffix'] or None,
                    phone=normalized['phone'] or None,
                    address_line1=normalized['address_line1'] or None,
                    address_line2=normalized['address_line2'] or None,
                    barangay=normalized['barangay'] or None,
                    city_municipality=normalized['city_municipality'] or None,
                    province=normalized['province'] or None,
                    region=normalized['region'] or None,
                    postal_code=normalized['postal_code'] or None,
                )
                new_user.set_password(normalized['password'])
                db.session.add(new_user)
                db.session.commit()
                from flask_login import login_user
                login_user(new_user)
                return redirect(url_for('shop'))
            except Exception:
                db.session.rollback()
                errors['general'] = 'Something went wrong. Please try again.'
                return render_template('auth/register_customer.html', errors=errors, form=normalized)
        return render_template('auth/register_customer.html', errors={}, form={})

    @app.route('/auth/register/seller', methods=['GET', 'POST'])
    def auth_register_seller():
        if request.method == 'POST':
            errors, normalized = validate_registration_payload(
                request.form,
                'seller',
                postal_lookup,
                email_exists=lambda email: User.query.filter_by(email=email).first() is not None,
            )

            business_permit_file = request.files.get('business_permit')
            barangay_permit_file = request.files.get('barangay_permit')
            mayors_permit_file = request.files.get('mayors_permit')

            business_permit_path = None
            barangay_permit_path = None
            mayors_permit_path = None

            if not business_permit_file or not business_permit_file.filename:
                errors['business_permit'] = 'Business permit file is required.'
            if not barangay_permit_file or not barangay_permit_file.filename:
                errors['barangay_permit'] = 'Barangay permit file is required.'
            if not mayors_permit_file or not mayors_permit_file.filename:
                errors['mayors_permit'] = 'Mayor\'s permit file is required.'

            if not errors:
                business_permit_path, upload_error = save_seller_permit(business_permit_file, 'business_permit')
                if upload_error:
                    errors['business_permit'] = upload_error
                barangay_permit_path, upload_error = save_seller_permit(barangay_permit_file, 'barangay_permit')
                if upload_error:
                    errors['barangay_permit'] = upload_error
                mayors_permit_path, upload_error = save_seller_permit(mayors_permit_file, 'mayors_permit')
                if upload_error:
                    errors['mayors_permit'] = upload_error

            if errors:
                return render_template('auth/register_seller.html', errors=errors, form=normalized)

            try:
                new_user = User(
                    email=normalized['email'],
                    role='seller',
                    full_name=normalized['full_name'],
                    first_name=normalized['first_name'] or None,
                    middle_name=normalized['middle_name'] or None,
                    last_name=normalized['last_name'] or None,
                    suffix=normalized['suffix'] or None,
                    phone=normalized['phone'] or None,
                    address_line1=normalized['address_line1'] or None,
                    address_line2=normalized['address_line2'] or None,
                    barangay=normalized['barangay'] or None,
                    city_municipality=normalized['city_municipality'] or None,
                    province=normalized['province'] or None,
                    region=normalized['region'] or None,
                    postal_code=normalized['postal_code'] or None,
                    business_name=normalized['business_name'] or None,
                    business_permit_path=business_permit_path,
                    barangay_permit_path=barangay_permit_path,
                    mayors_permit_path=mayors_permit_path,
                    seller_verification_status='pending',
                )
                new_user.set_password(normalized['password'])
                db.session.add(new_user)
                db.session.commit()
                from flask_login import login_user
                login_user(new_user)
                flash('Seller account created. Your permits are submitted for verification.', 'success')
                return redirect(url_for('seller_dashboard'))
            except Exception:
                db.session.rollback()
                errors['general'] = 'Something went wrong. Please try again.'
                return render_template('auth/register_seller.html', errors=errors, form=normalized)

        return render_template('auth/register_seller.html', errors={}, form={})

    @app.route('/auth/logout')
    def auth_logout():
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('index'))

    @app.route('/terms')
    def terms_of_service():
        return render_template('terms.html')

    @app.route('/privacy')
    def privacy_policy():
        return render_template('privacy.html')

    # Customer Portal Routes (Aliased for /customer/* paths)
    @app.route('/customer/home')
    def customer_home():
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
        cat_rows = db.session.query(Product.category).filter(
            Product.is_active.is_(True),
            Product.category.isnot(None),
            Product.category != '',
        ).distinct().order_by(Product.category.asc()).all()
        shop_categories = [r[0] for r in cat_rows if r[0]]
        return render_template(
            'customer/home.html',
            view_mode='discovery',
            products=products,
            shop_categories=shop_categories,
            shop_active_category='',
        )

    @app.route('/shop')
    def shop():
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        category = (request.args.get('category') or '').strip()
        products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
        cat_rows = db.session.query(Product.category).filter(
            Product.is_active.is_(True),
            Product.category.isnot(None),
            Product.category != '',
        ).distinct().order_by(Product.category.asc()).all()
        shop_categories = [r[0] for r in cat_rows if r[0]]
        return render_template(
            'customer/home.html',
            view_mode='catalog',
            products=products,
            shop_categories=shop_categories,
            shop_active_category=category,
        )

    @app.route('/customer/product/<ref>')
    @app.route('/products/<ref>')
    def product_detail(ref):
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        product = Product.query.filter_by(product_ref=ref, is_active=True).first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('shop'))

        related_products = Product.query.filter(
            Product.is_active.is_(True),
            Product.category == product.category,
            Product.id != product.id,
        ).order_by(Product.created_at.desc()).limit(4).all()
        return render_template('customer/product_detail.html', product=product, related_products=related_products)

    @app.route('/customer/cart', methods=['GET', 'POST'])
    @app.route('/cart', methods=['GET', 'POST'])
    def cart():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.cart import Cart
            from .models.product import Product
            from .models.voucher import Voucher
            from .models.order import Order
        except Exception:
            from models.cart import Cart
            from models.product import Product
            from models.voucher import Voucher
            from models.order import Order

        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if cart is None:
            cart = Cart(user_id=current_user.id, items=[])
            db.session.add(cart)
            db.session.commit()

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            items = [dict(entry) for entry in (cart.items or [])]
            if action == 'add':
                product_id = request.form.get('product_id', type=int)
                product_ref = (request.form.get('product_ref') or '').strip()
                product = None
                if product_id:
                    product = Product.query.get(product_id)
                elif product_ref:
                    product = Product.query.filter_by(product_ref=product_ref).first()

                if not product:
                    flash('Product not found.', 'error')
                elif int(getattr(product, 'stock', 0) or 0) <= 0:
                    flash('This product is out of stock.', 'error')
                else:
                    max_stock = int(product.stock or 0)
                    qty_errors, qty_data = validate_cart_quantity_payload(request.form, max_stock=max_stock)
                    qty = qty_data['qty']

                    if qty_errors.get('qty'):
                        flash(qty_errors['qty'], 'warning')

                    existing = None
                    for item in items:
                        if int(item.get('product_id')) == int(product.id):
                            existing = item
                            break

                    if existing:
                        existing['qty'] = min(max_stock, max(int(existing.get('qty') or 1), 1) + qty)
                    else:
                        items.append({'product_id': int(product.id), 'qty': min(max_stock, qty)})

                    cart.items = items
                    db.session.commit()
                    flash('Item added to cart.', 'success')

                next_path = (request.form.get('next') or '').strip()
                if next_path.startswith('/'):
                    return redirect(next_path)
            elif action == 'update':
                product_id = request.form.get('product_id', type=int)
                updated = False
                product = Product.query.get(product_id) if product_id else None
                if product:
                    qty_errors, qty_data = validate_cart_quantity_payload(request.form, max_stock=int(product.stock or 0))
                    qty = qty_data['qty']
                    if qty_errors.get('qty'):
                        flash(qty_errors['qty'], 'warning')
                else:
                    qty_errors, qty_data = validate_cart_quantity_payload(request.form)
                    qty = qty_data['qty']
                    if qty_errors.get('qty'):
                        flash(qty_errors['qty'], 'warning')
                for item in items:
                    if int(item.get('product_id')) == int(product_id):
                        item['qty'] = qty
                        updated = True
                        break
                if updated:
                    cart.items = items
                    db.session.commit()
                    flash('Cart updated.', 'success')
            elif action == 'remove':
                product_id = request.form.get('product_id', type=int)
                cart.items = [item for item in items if int(item.get('product_id')) != int(product_id)]
                db.session.commit()
                flash('Item removed from cart.', 'success')
            elif action == 'clear':
                cart.items = []
                cart.voucher_code = None
                db.session.commit()
                flash('Cart cleared.', 'success')
            elif action == 'apply_voucher':
                voucher_code = (request.form.get('voucher_code') or '').strip()
                preview_lines = []
                preview_subtotal = 0.0
                for entry in items:
                    product = Product.query.get(entry.get('product_id'))
                    if not product:
                        continue
                    quantity = max(int(entry.get('qty') or 1), 1)
                    line_total = float(product.price or 0) * quantity
                    preview_subtotal += line_total
                    preview_lines.append({'product': product, 'qty': quantity, 'line_total': line_total})

                voucher, normalized_code, _, error_message = validate_voucher_for_cart(
                    voucher_code=voucher_code,
                    cart_items=preview_lines,
                    subtotal=preview_subtotal,
                    customer_id=current_user.id,
                    VoucherModel=Voucher,
                    OrderModel=Order,
                )
                if voucher:
                    cart.voucher_code = normalized_code
                    db.session.commit()
                    flash(f'Voucher {normalized_code} applied.', 'success')
                else:
                    cart.voucher_code = None
                    db.session.commit()
                    flash(error_message or 'Could not apply voucher.', 'error')
            elif action == 'remove_voucher':
                cart.voucher_code = None
                db.session.commit()
                flash('Voucher removed.', 'success')
            return redirect(url_for('cart'))

        cart_lines = []
        subtotal = 0.0
        for entry in cart.items or []:
            product = Product.query.get(entry.get('product_id'))
            if not product:
                continue
            quantity = max(int(entry.get('qty') or 1), 1)
            line_total = float(product.price or 0) * quantity
            subtotal += line_total
            cart_lines.append({'product': product, 'qty': quantity, 'line_total': line_total})

        applied_voucher = None
        voucher_code = ''
        voucher_discount = 0.0
        if cart.voucher_code:
            voucher, normalized_code, discount_value, error_message = validate_voucher_for_cart(
                voucher_code=cart.voucher_code,
                cart_items=cart_lines,
                subtotal=subtotal,
                customer_id=current_user.id,
                VoucherModel=Voucher,
                OrderModel=Order,
            )
            if voucher:
                applied_voucher = voucher
                voucher_code = normalized_code
                voucher_discount = discount_value
            else:
                cart.voucher_code = None
                db.session.commit()
                if error_message:
                    flash(error_message, 'warning')

        subtotal = money(subtotal)
        voucher_discount = money(voucher_discount)
        grand_total = money(max(subtotal - voucher_discount, 0.0))
        return render_template(
            'customer/cart.html',
            cart_lines=cart_lines,
            subtotal=subtotal,
            has_items=bool(cart_lines),
            voucher_code=voucher_code,
            voucher_discount=voucher_discount,
            applied_voucher=applied_voucher,
            grand_total=grand_total,
        )

    @app.route('/customer/checkout', methods=['GET', 'POST'])
    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.cart import Cart
            from .models.order import Order, OrderItem
            from .models.product import Product
            from .models.voucher import Voucher
            from .models.loyalty import LoyaltyTransaction
            from .models.installment import InstallmentPlan, InstallmentSchedule
        except Exception:
            from models.cart import Cart
            from models.order import Order, OrderItem
            from models.product import Product
            from models.voucher import Voucher
            from models.loyalty import LoyaltyTransaction
            from models.installment import InstallmentPlan, InstallmentSchedule

        cart = Cart.query.filter_by(user_id=current_user.id).first()
        cart_items = []
        subtotal = 0.0
        if cart and cart.items:
            for entry in cart.items:
                product = Product.query.get(entry.get('product_id'))
                if not product:
                    continue
                quantity = max(int(entry.get('qty') or 1), 1)
                line_total = money(float(product.price or 0) * quantity)
                subtotal += line_total
                cart_items.append({'product': product, 'qty': quantity, 'line_total': line_total})

        voucher_code = ''
        voucher_discount = 0.0
        voucher = None
        loyalty_requested = 0
        loyalty_applied = 0
        available_points = int(getattr(current_user, 'loyalty_points', 0) or 0)

        def normalize_payment(value):
            raw_value = (value or 'full_pay').strip()
            if raw_value in ('credit', 'wallet', 'cod'):
                return 'full_pay'
            if raw_value == 'installment':
                return 'installment'
            return 'full_pay'

        if request.method == 'POST':
            selected_payment = normalize_payment(request.form.get('payment'))
        else:
            selected_payment = normalize_payment(request.args.get('payment'))

        checkout_errors = {}
        checkout_form = {
            'recipient_name': current_user.computed_full_name or current_user.full_name or '',
            'address_line1': ', '.join([
                part for part in [
                    current_user.address_line1,
                    current_user.address_line2,
                    current_user.barangay,
                    current_user.city_municipality,
                    current_user.province,
                    current_user.region,
                ] if part
            ]),
            'postal_code': current_user.postal_code or '',
            'phone': (current_user.phone or '').replace('+63', ''),
            'plan_months': 12,
        }

        if request.method == 'POST':
            checkout_form.update({
                'recipient_name': (request.form.get('recipient_name') or '').strip(),
                'address_line1': (request.form.get('address_line1') or request.form.get('address') or '').strip(),
                'postal_code': (request.form.get('postal_code') or '').strip(),
                'phone': (request.form.get('phone') or '').strip(),
            })
            try:
                posted_plan = int(request.form.get('plan') or 12)
                if posted_plan in (6, 12, 24):
                    checkout_form['plan_months'] = posted_plan
            except Exception:
                checkout_form['plan_months'] = 12

        if request.method == 'POST':
            voucher_code = (request.form.get('voucher_code') or '').strip()
            loyalty_requested = max(request.form.get('loyalty_points', type=int) or 0, 0)
        else:
            voucher_code = (request.args.get('voucher_code') or (cart.voucher_code if cart else '') or '').strip()
            loyalty_requested = max(request.args.get('loyalty_points', type=int) or 0, 0)

        if voucher_code:
            voucher, normalized_code, voucher_discount, error_message = validate_voucher_for_cart(
                voucher_code=voucher_code,
                cart_items=cart_items,
                subtotal=subtotal,
                customer_id=current_user.id,
                VoucherModel=Voucher,
                OrderModel=Order,
            )
            if voucher:
                voucher_code = normalized_code
                if cart:
                    cart.voucher_code = voucher_code
            else:
                voucher_code = ''
                if cart:
                    cart.voucher_code = None
                if request.method == 'POST' and error_message:
                    flash(error_message, 'error')
        elif cart and cart.voucher_code:
            cart.voucher_code = None

        subtotal = money(subtotal)
        voucher_discount = money(voucher_discount)
        max_loyalty_value = max(subtotal - voucher_discount, 0.0)
        loyalty_applied = min(loyalty_requested, available_points, int(max_loyalty_value))
        discount_total = money(voucher_discount + float(loyalty_applied))
        order_total = money(max(subtotal - discount_total, 0.0))
        earned_points = int(order_total // 100)

        if request.method == 'POST':
            if not cart_items:
                flash('Your cart is empty.', 'error')
                return redirect(url_for('cart'))

            checkout_action = (request.form.get('action') or 'place_order').strip()
            if checkout_action != 'place_order':
                return render_template(
                    'customer/checkout.html',
                    cart_items=cart_items,
                    subtotal=subtotal,
                    voucher_code=voucher_code,
                    voucher_discount=voucher_discount,
                    loyalty_requested=int(loyalty_requested),
                    loyalty_applied=int(loyalty_applied),
                    available_points=int(available_points),
                    order_total=order_total,
                    earned_points=int(earned_points),
                    selected_payment=selected_payment,
                    checkout_form=checkout_form,
                    checkout_errors=checkout_errors,
                )

            checkout_errors, checkout_data = validate_checkout_payload(request.form)
            if checkout_errors:
                return render_template(
                    'customer/checkout.html',
                    cart_items=cart_items,
                    subtotal=subtotal,
                    voucher_code=voucher_code,
                    voucher_discount=voucher_discount,
                    loyalty_requested=int(loyalty_requested),
                    loyalty_applied=int(loyalty_applied),
                    available_points=int(available_points),
                    order_total=order_total,
                    earned_points=int(earned_points),
                    selected_payment=selected_payment,
                    checkout_form=checkout_form,
                    checkout_errors=checkout_errors,
                )

            checkout_form.update({
                'recipient_name': checkout_data['recipient_name'],
                'address_line1': checkout_data['address_line1'],
                'postal_code': checkout_data['postal_code'],
                'phone': checkout_data['phone'],
                'plan_months': checkout_data['plan_months'],
            })

            payment_method = checkout_data['payment_method']
            selected_payment = payment_method

            if payment_method == 'installment':
                if not all(bool(getattr(line['product'], 'installment_enabled', False)) for line in cart_items):
                    checkout_errors['payment'] = 'One or more items in your cart are not eligible for installment.'
                    return render_template(
                        'customer/checkout.html',
                        cart_items=cart_items,
                        subtotal=subtotal,
                        voucher_code=voucher_code,
                        voucher_discount=voucher_discount,
                        loyalty_requested=int(loyalty_requested),
                        loyalty_applied=int(loyalty_applied),
                        available_points=int(available_points),
                        order_total=order_total,
                        earned_points=int(earned_points),
                        selected_payment=selected_payment,
                        checkout_form=checkout_form,
                        checkout_errors=checkout_errors,
                    )

            plan_months = checkout_data['plan_months']
            address = {
                'recipient_name': checkout_data['recipient_name'],
                'address_line1': checkout_data['address_line1'],
                'address_line2': checkout_data['address_line2'],
                'barangay': checkout_data['barangay'],
                'city_municipality': checkout_data['city_municipality'],
                'province': checkout_data['province'],
                'region': checkout_data['region'],
                'postal_code': checkout_data['postal_code'],
                'country': checkout_data['country'],
                'phone': checkout_data['phone'] or current_user.phone or '',
            }

            try:
                order_ref = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex[:4].upper()}"
                order = Order(
                    order_ref=order_ref,
                    customer_id=current_user.id,
                    status='paid' if payment_method == 'full_pay' else 'pending',
                    subtotal=money(subtotal),
                    discount=discount_total,
                    shipping_fee=0,
                    tax=0,
                    total=money(order_total),
                    voucher_id=voucher.id if voucher else None,
                    loyalty_redeemed=loyalty_applied,
                    payment_method=payment_method,
                    shipping_address=address,
                    notes=f"Created from customer checkout{' | voucher=' + voucher.code if voucher else ''}",
                    paid_at=datetime.utcnow() if payment_method == 'full_pay' else None,
                )
                db.session.add(order)
                db.session.flush()
                for line in cart_items:
                    available_stock = int(line['product'].stock or 0)
                    if int(line['qty']) > available_stock:
                        raise ValueError(f"Insufficient stock for {line['product'].name}. Available: {available_stock}.")

                    db.session.add(OrderItem(
                        order_id=order.id,
                        product_id=line['product'].id,
                        quantity=line['qty'],
                        unit_price=line['product'].price,
                        subtotal=money(line['line_total']),
                    ))
                    line['product'].stock = available_stock - int(line['qty'])

                if payment_method == 'installment':
                    monthly_amount = round(float(order_total) / float(plan_months), 2) if plan_months > 0 else float(order_total)
                    plan = InstallmentPlan(
                        order_id=order.id,
                        months=plan_months,
                        monthly_amount=monthly_amount,
                        downpayment=0,
                        total_interest=0,
                        status='active',
                    )
                    db.session.add(plan)
                    db.session.flush()

                    today = datetime.utcnow().date()
                    for month_idx in range(plan_months):
                        due_date = today + timedelta(days=30 * (month_idx + 1))
                        db.session.add(InstallmentSchedule(
                            plan_id=plan.id,
                            due_date=due_date,
                            amount=monthly_amount,
                            status='pending',
                        ))

                if voucher:
                    voucher.uses_count = int(voucher.uses_count or 0) + 1

                if loyalty_applied > 0:
                    current_user.loyalty_points = max(int(current_user.loyalty_points or 0) - int(loyalty_applied), 0)
                    db.session.add(LoyaltyTransaction(
                        user_id=current_user.id,
                        type='redeem',
                        points=int(loyalty_applied),
                        reference=order_ref,
                        note='Redeemed at checkout',
                    ))

                if earned_points > 0:
                    current_user.loyalty_points = int(current_user.loyalty_points or 0) + int(earned_points)
                    db.session.add(LoyaltyTransaction(
                        user_id=current_user.id,
                        type='earn',
                        points=int(earned_points),
                        reference=order_ref,
                        note='Earned from checkout',
                    ))

                if order.status == 'paid':
                    ensure_invoice_for_order(order)

                cart.items = []
                cart.voucher_code = None
                db.session.commit()
                return redirect(url_for('checkout_success', order_ref=order_ref))
            except Exception as ex:
                db.session.rollback()
                if isinstance(ex, ValueError):
                    checkout_errors['general'] = str(ex)
                else:
                    checkout_errors['general'] = 'Could not place your order. Please try again.'
                return render_template(
                    'customer/checkout.html',
                    cart_items=cart_items,
                    subtotal=subtotal,
                    voucher_code=voucher_code,
                    voucher_discount=voucher_discount,
                    loyalty_requested=int(loyalty_requested),
                    loyalty_applied=int(loyalty_applied),
                    available_points=int(available_points),
                    order_total=order_total,
                    earned_points=int(earned_points),
                    selected_payment=selected_payment,
                    checkout_form=checkout_form,
                    checkout_errors=checkout_errors,
                )

        return render_template(
            'customer/checkout.html',
            cart_items=cart_items,
            subtotal=subtotal,
            voucher_code=voucher_code,
            voucher_discount=voucher_discount,
            loyalty_requested=int(loyalty_requested),
            loyalty_applied=int(loyalty_applied),
            available_points=int(available_points),
            order_total=order_total,
            earned_points=int(earned_points),
            selected_payment=selected_payment,
            checkout_form=checkout_form,
            checkout_errors=checkout_errors,
        )

    @app.route('/customer/checkout/success')
    def checkout_success():
        order_ref = request.args.get('order_ref', 'ORD-000000')
        return render_template('customer/checkout_success.html', order_ref=order_ref)

    @app.route('/customer/orders')
    def customer_orders():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = Order.query.filter(Order.customer_id == current_user.id)
        if q:
            like_q = f"%{q}%"
            query = query.filter((Order.order_ref.ilike(like_q)) | (Order.notes.ilike(like_q)))
        if status_filter != 'all':
            query = query.filter(Order.status == status_filter)

        orders = query.order_by(Order.created_at.desc()).all()
        return_map = {item.order_id: item for item in ReturnRequest.query.filter(ReturnRequest.customer_id == current_user.id).all()}

        stats = {
            'total': len(orders),
            'pending': sum(1 for order in orders if order.status == 'pending'),
            'shipped': sum(1 for order in orders if order.status == 'shipped'),
            'delivered': sum(1 for order in orders if order.status == 'delivered'),
        }
        return render_template('customer/orders.html', orders=orders, return_map=return_map, stats=stats, filters={'q': q, 'status': status_filter})

    @app.route('/customer/orders/<order_ref>')
    def customer_order_detail(order_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first()
        if not order:
            flash('Order not found.', 'error')
            return redirect(url_for('customer_orders'))

        existing_return = ReturnRequest.query.filter_by(order_id=order.id, customer_id=current_user.id).first()
        return render_template('customer/order_detail.html', order=order, existing_return=existing_return)

    @app.route('/customer/invoices')
    def customer_invoices():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.invoice import Invoice
        except Exception:
            from models.invoice import Invoice

        invoices = Invoice.query.filter_by(customer_id=current_user.id).order_by(Invoice.issued_at.desc()).all()
        return render_template('customer/invoices.html', invoices=invoices)

    @app.route('/customer/invoices/<invoice_ref>')
    def customer_invoice_detail(invoice_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.invoice import Invoice
        except Exception:
            from models.invoice import Invoice

        invoice = Invoice.query.filter_by(invoice_ref=invoice_ref, customer_id=current_user.id).first()
        if not invoice:
            flash('Invoice not found.', 'error')
            return redirect(url_for('customer_invoices'))
        return render_template('customer/invoice_detail.html', invoice=invoice)

    @app.route('/customer/returns', methods=['GET', 'POST'])
    def customer_returns():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        return_errors = {}
        return_form = {'order_ref': '', 'reason': '', 'description': ''}

        if request.method == 'POST':
            return_errors, return_data = validate_return_payload(request.form)
            return_form.update(return_data)
            order_ref = return_data['order_ref']
            reason = return_data['reason']
            description = return_data['description']
            order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first() if order_ref else None
            if order_ref and not order:
                return_errors['order_ref'] = 'Please choose one of your own orders.'

            if not return_errors:
                try:
                    ts = datetime.utcnow().strftime('%y%m%d%H%M%S')
                    rrt_ref = f'RET-{current_user.id}-{ts}'
                    refund_amount = calculate_refund_amount(order)
                    item = ReturnRequest(
                        rrt_ref=rrt_ref,
                        order_id=order.id,
                        customer_id=current_user.id,
                        reason=reason,
                        description=description,
                        status='pending',
                        refund_amount=refund_amount,
                    )
                    db.session.add(item)
                    db.session.commit()
                    flash(f'Return request {rrt_ref} submitted.', 'success')
                    return redirect(url_for('customer_returns'))
                except Exception:
                    db.session.rollback()
                    return_errors['general'] = 'Could not submit return request.'
            else:
                flash('Please correct the highlighted return form fields.', 'error')

        orders = Order.query.filter(Order.customer_id == current_user.id).order_by(Order.created_at.desc()).all()
        returns = ReturnRequest.query.filter(ReturnRequest.customer_id == current_user.id).order_by(ReturnRequest.created_at.desc()).all()
        return render_template('customer/returns.html', orders=orders, returns=returns, errors=return_errors, form=return_form)

    @app.route('/customer/loyalty')
    def customer_loyalty():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.loyalty import LoyaltyTransaction
            from .models.voucher import Voucher
            from .models.order import Order
        except Exception:
            from models.loyalty import LoyaltyTransaction
            from models.voucher import Voucher
            from models.order import Order

        transactions = LoyaltyTransaction.query.filter_by(user_id=current_user.id).order_by(LoyaltyTransaction.created_at.desc()).limit(20).all()
        available_vouchers = Voucher.query.filter(Voucher.is_active.is_(True)).order_by(Voucher.id.desc()).limit(12).all()

        claimed_voucher_ids = set()
        for order in Order.query.filter_by(customer_id=current_user.id).filter(Order.voucher_id.isnot(None)).all():
            claimed_voucher_ids.add(order.voucher_id)

        voucher_cards = []
        now = datetime.utcnow()
        for voucher in available_vouchers:
            days_left = None
            if voucher.valid_until:
                days_left = (voucher.valid_until.date() - now.date()).days
            voucher_cards.append({
                'voucher': voucher,
                'claimed': voucher.id in claimed_voucher_ids,
                'days_left': days_left,
                'is_expiring': days_left is not None and days_left <= 3,
            })

        stats = {
            'points_balance': int(current_user.loyalty_points or 0),
            'available_vouchers': sum(1 for row in voucher_cards if not row['claimed']),
            'expiring_soon': sum(1 for row in voucher_cards if row['is_expiring'] and not row['claimed']),
            'earned_total': sum(int(item.points or 0) for item in transactions if item.type == 'earn'),
            'redeemed_total': sum(int(item.points or 0) for item in transactions if item.type == 'redeem'),
        }
        return render_template('customer/loyalty.html', stats=stats, voucher_cards=voucher_cards, transactions=transactions)

    @app.route('/customer/profile')
    def customer_profile():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        customer_orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
        recent_orders = customer_orders[:5]
        returns_count = ReturnRequest.query.filter_by(customer_id=current_user.id).count()
        profile_stats = {
            'total_orders': len(customer_orders),
            'pending_orders': sum(1 for order in customer_orders if order.status in ('pending', 'paid', 'packed', 'shipped')),
            'delivered_orders': sum(1 for order in customer_orders if order.status == 'delivered'),
            'returns': returns_count,
            'total_spent': sum(float(order.total or 0) for order in customer_orders if order.status in ('paid', 'packed', 'shipped', 'delivered', 'refunded')),
        }
        return render_template('customer/profile.html', profile_stats=profile_stats, recent_orders=recent_orders)

    @app.route('/customer/profile/edit', methods=['GET', 'POST'])
    def customer_profile_edit():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        if request.method == 'POST':
            profile_errors, profile_data = validate_profile_payload(request.form, postal_lookup)
            if profile_errors:
                return render_template('customer/profile_form.html', errors=profile_errors, form=profile_data)

            current_user.first_name = profile_data['first_name']
            current_user.middle_name = profile_data['middle_name'] or None
            current_user.last_name = profile_data['last_name']
            current_user.suffix = profile_data['suffix'] or None
            current_user.full_name = profile_data['full_name']
            current_user.phone = profile_data['phone'] or None

            current_user.address_line1 = profile_data['address_line1'] or None
            current_user.address_line2 = profile_data['address_line2'] or None
            current_user.barangay = profile_data['barangay'] or None
            current_user.city_municipality = profile_data['city_municipality'] or None
            current_user.province = profile_data['province'] or None
            current_user.region = profile_data['region'] or None
            current_user.postal_code = profile_data['postal_code'] or None
            try:
                db.session.commit()
                flash('Profile updated.', 'success')
                return redirect(url_for('customer_profile'))
            except Exception:
                db.session.rollback()
                profile_errors = {'general': 'Could not update profile.'}
                return render_template('customer/profile_form.html', errors=profile_errors, form=profile_data)

        form_data = {
            'first_name': current_user.first_name or '',
            'middle_name': current_user.middle_name or '',
            'last_name': current_user.last_name or '',
            'suffix': current_user.suffix or '',
            'phone': current_user.phone or '',
            'address_line1': current_user.address_line1 or '',
            'address_line2': current_user.address_line2 or '',
            'barangay': current_user.barangay or '',
            'city_municipality': current_user.city_municipality or '',
            'province': current_user.province or '',
            'region': current_user.region or '',
            'postal_code': current_user.postal_code or '',
        }
        return render_template('customer/profile_form.html', errors={}, form=form_data)

    @app.route('/customer/wishlist')
    def customer_wishlist():
        # Using home template as placeholder for now
        return render_template('customer/home.html')

    @app.route('/about')
    def about():
        return render_template('static_pages.html', **static_page_payload('about', 'About E-ACIS'))

    @app.route('/contact')
    def contact():
        return render_template('static_pages.html', **static_page_payload('contact', 'Contact Us'))

    @app.route('/terms')
    def terms():
        return render_template('static_pages.html', **static_page_payload('terms', 'Terms of Service'))

    @app.route('/privacy')
    def privacy():
        return render_template('static_pages.html', **static_page_payload('privacy', 'Privacy Policy'))

    # Seller preview routes (static templates)
    @app.route('/seller/dashboard')
    def seller_dashboard():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
            from .models.order import Order, OrderItem
            from .models.inquiry_ticket import InquiryTicket
        except Exception:
            from models.product import Product
            from models.order import Order, OrderItem
            from models.inquiry_ticket import InquiryTicket

        products = Product.query.filter_by(seller_id=current_user.id).all()
        seller_orders = db.session.query(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().order_by(Order.created_at.desc()).all()
        revenue_today = sum(float(order.total or 0) for order in seller_orders if order.created_at and order.created_at.date() == datetime.utcnow().date())
        pending_orders = sum(1 for order in seller_orders if order.status in ('pending', 'paid', 'packed'))
        active_products = sum(1 for product in products if product.is_active)
        low_stock = sum(1 for product in products if (product.stock or 0) <= (product.low_stock_threshold or 0))
        open_inquiries = InquiryTicket.query.filter_by(assigned_to=current_user.id, status='open').count()

        kpis = {
            'revenue_today': revenue_today,
            'pending_orders': pending_orders,
            'active_products': active_products,
            'low_stock': low_stock,
            'open_inquiries': open_inquiries,
        }
        recent_orders = seller_orders[:5]
        verification_status = getattr(current_user, 'seller_verification_status', None) if current_user and getattr(current_user, 'is_authenticated', False) else None
        return render_template('seller/dashboard.html', verification_status=verification_status, kpis=kpis, recent_orders=recent_orders)

    @app.route('/seller/products')
    def seller_products():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip()
        query = Product.query.filter(Product.seller_id == current_user.id)
        if q:
            like_q = f"%{q}%"
            query = query.filter(
                (Product.product_ref.ilike(like_q))
                | (Product.name.ilike(like_q))
                | (Product.category.ilike(like_q))
            )
        if status_filter == 'active':
            query = query.filter(Product.is_active.is_(True))
        elif status_filter == 'inactive':
            query = query.filter(Product.is_active.is_(False))
        elif status_filter == 'low_stock':
            query = query.filter(Product.stock <= Product.low_stock_threshold)

        products = query.order_by(Product.created_at.desc()).all()
        stats = {
            'total': Product.query.filter(Product.seller_id == current_user.id).count(),
            'active': Product.query.filter(Product.seller_id == current_user.id, Product.is_active.is_(True)).count(),
            'low_stock': Product.query.filter(Product.seller_id == current_user.id, Product.stock <= Product.low_stock_threshold).count(),
            'installment_enabled': Product.query.filter(Product.seller_id == current_user.id, Product.installment_enabled.is_(True)).count(),
        }
        return render_template('seller/products.html', products=products, stats=stats, filters={'q': q, 'status': status_filter})

    @app.route('/seller/products/new')
    @app.route('/seller/products/create')
    @app.route('/seller/product/create')
    def seller_product_create():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        return render_template('seller/product_form.html', ref=None, product=None, errors={}, form={})

    @app.route('/seller/products/new', methods=['POST'])
    @app.route('/seller/products/create', methods=['POST'])
    @app.route('/seller/product/create', methods=['POST'])
    def seller_product_create_post():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        errors, form_data = validate_seller_product_payload(request.form)
        if errors:
            flash(' '.join(errors.values()), 'error')
            form_product = {
                'name': form_data['name'],
                'category': form_data['category'],
                'description': form_data['description'],
                'price': form_data['price_raw'],
                'stock': form_data['stock_raw'],
                'warranty_months': form_data['warranty_raw'],
                'is_active': form_data['is_active'],
                'installment_enabled': form_data['installment_enabled'],
            }
            return render_template('seller/product_form.html', ref=None, product=form_product, errors=errors, form=form_product)

        ts = datetime.utcnow().strftime('%y%m%d%H%M%S')
        product_ref = f"PRD-S{current_user.id}-{ts}"
        try:
            product = Product(
                product_ref=product_ref,
                seller_id=current_user.id,
                name=form_data['name'],
                category=form_data['category'],
                description=form_data['description'],
                price=form_data['price'],
                stock=form_data['stock'],
                warranty_months=form_data['warranty_months'],
                installment_enabled=form_data['installment_enabled'],
                is_active=form_data['is_active'],
            )
            db.session.add(product)
            db.session.commit()
            flash(f'Product {product_ref} created successfully.', 'success')
            return redirect(url_for('seller_products'))
        except Exception:
            db.session.rollback()
            flash('Unable to create product right now.', 'error')
            form_product = {
                'name': form_data['name'],
                'category': form_data['category'],
                'description': form_data['description'],
                'price': form_data['price_raw'],
                'stock': form_data['stock_raw'],
                'warranty_months': form_data['warranty_raw'],
                'is_active': form_data['is_active'],
                'installment_enabled': form_data['installment_enabled'],
            }
            return render_template(
                'seller/product_form.html',
                ref=None,
                product=form_product,
                errors={'general': 'Unable to create product right now.'},
                form=form_product,
            )

    @app.route('/seller/products/<ref>')
    @app.route('/seller/products/<ref>/edit')
    def seller_product_detail(ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        product = Product.query.filter_by(product_ref=ref, seller_id=current_user.id).first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('seller_products'))
        return render_template('seller/product_form.html', ref=ref, product=product, errors={}, form={})

    @app.route('/seller/products/<ref>/edit', methods=['POST'])
    def seller_product_detail_post(ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        product = Product.query.filter_by(product_ref=ref, seller_id=current_user.id).first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('seller_products'))

        errors, form_data = validate_seller_product_payload(request.form)
        if errors:
            flash(' '.join(errors.values()), 'error')
            form_product = {
                'name': form_data['name'],
                'category': form_data['category'],
                'description': form_data['description'],
                'price': form_data['price_raw'],
                'stock': form_data['stock_raw'],
                'warranty_months': form_data['warranty_raw'],
                'is_active': form_data['is_active'],
                'installment_enabled': form_data['installment_enabled'],
            }
            return render_template('seller/product_form.html', ref=ref, product=form_product, errors=errors, form=form_product)

        try:
            product.name = form_data['name']
            product.category = form_data['category']
            product.description = form_data['description']
            product.price = form_data['price']
            product.stock = form_data['stock']
            product.warranty_months = form_data['warranty_months']
            product.is_active = form_data['is_active']
            product.installment_enabled = form_data['installment_enabled']
            db.session.commit()
            flash(f'Product {ref} updated.', 'success')
            return redirect(url_for('seller_product_detail', ref=ref))
        except Exception:
            db.session.rollback()
            flash('Unable to update product.', 'error')
            form_product = {
                'name': form_data['name'],
                'category': form_data['category'],
                'description': form_data['description'],
                'price': form_data['price_raw'],
                'stock': form_data['stock_raw'],
                'warranty_months': form_data['warranty_raw'],
                'is_active': form_data['is_active'],
                'installment_enabled': form_data['installment_enabled'],
            }
            return render_template(
                'seller/product_form.html',
                ref=ref,
                product=form_product,
                errors={'general': 'Unable to update product.'},
                form=form_product,
            )

    @app.route('/seller/products/<ref>/delete', methods=['POST'])
    def seller_product_delete(ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        product = Product.query.filter_by(product_ref=ref, seller_id=current_user.id).first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('seller_products'))
        try:
            db.session.delete(product)
            db.session.commit()
            flash(f'Product {ref} deleted.', 'success')
        except Exception:
            db.session.rollback()
            flash('Unable to delete product. It may be linked to existing orders.', 'error')
        return redirect(url_for('seller_products'))

    @app.route('/seller/inventory')
    def seller_inventory():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        products = Product.query.filter_by(seller_id=current_user.id).order_by(Product.created_at.desc()).all()
        low_stock_items = [product for product in products if (product.stock or 0) <= (product.low_stock_threshold or 0)]
        out_of_stock_items = [product for product in products if (product.stock or 0) <= 0]
        stats = {
            'low_stock': len(low_stock_items),
            'out_of_stock': len(out_of_stock_items),
            'restock_queue': len(low_stock_items),
            'total_products': len(products),
        }
        return render_template('seller/inventory.html', stats=stats, low_stock_items=low_stock_items[:20])

    @app.route('/seller/orders')
    def seller_orders():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        order_ids_query = db.session.query(Order.id).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id)
        if q:
            like_q = f"%{q}%"
            order_ids_query = order_ids_query.filter((Order.order_ref.ilike(like_q)) | (Order.customer.has(User.full_name.ilike(like_q))) | (Order.customer.has(User.email.ilike(like_q))))
        if status_filter != 'all':
            order_ids_query = order_ids_query.filter(Order.status == status_filter)

        order_ids = [row[0] for row in order_ids_query.distinct().all()]
        orders = Order.query.filter(Order.id.in_(order_ids)).order_by(Order.created_at.desc()).all() if order_ids else []

        stats = {
            'total': len(orders),
            'pending': sum(1 for order in orders if order.status == 'pending'),
            'shipped': sum(1 for order in orders if order.status == 'shipped'),
            'delivered': sum(1 for order in orders if order.status == 'delivered'),
        }

        return render_template('seller/orders.html', orders=orders, stats=stats, filters={'q': q, 'status': status_filter})

    @app.route('/seller/customer-orders')
    def seller_customer_orders():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        return redirect(url_for('seller_orders'))

    @app.route('/seller/orders/<order_ref>')
    def seller_order_detail(order_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product

        order = Order.query.filter_by(order_ref=order_ref).first()
        if not order:
            flash('Order not found.', 'error')
            return redirect(url_for('seller_orders'))

        seller_items = []
        for item in order.items.all():
            if item.product and item.product.seller_id == current_user.id:
                seller_items.append(item)

        if not seller_items:
            flash('You do not have access to this order.', 'error')
            return redirect(url_for('seller_orders'))

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            if action == 'update_status':
                new_status = (request.form.get('status') or '').strip()
                allowed = ('pending', 'paid', 'packed', 'shipped', 'delivered', 'past_due', 'refunded', 'cancelled')
                if new_status not in allowed:
                    flash('Invalid order status.', 'error')
                else:
                    try:
                        order.status = new_status
                        if new_status == 'paid' and not order.paid_at:
                            order.paid_at = datetime.utcnow()
                        elif new_status == 'shipped' and not order.shipped_at:
                            order.shipped_at = datetime.utcnow()
                        elif new_status == 'delivered' and not order.delivered_at:
                            order.delivered_at = datetime.utcnow()
                        if new_status == 'shipped' and not order.tracking_number:
                            order.tracking_number = f'TRK-{order.order_ref[-6:]}'
                        if new_status == 'paid':
                            ensure_invoice_for_order(order)
                        db.session.commit()
                        flash(f'Order {order.order_ref} updated to {new_status}.', 'success')
                    except Exception:
                        db.session.rollback()
                        flash('Could not update order status.', 'error')
                return redirect(url_for('seller_order_detail', order_ref=order_ref))

        return render_template('seller/order_detail.html', order=order, seller_items=seller_items)

    @app.route('/seller/orders/<order_ref>', methods=['POST'])
    def seller_order_detail_post(order_ref):
        return seller_order_detail(order_ref)

    @app.route('/seller/returns')
    def seller_returns():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.return_request import ReturnRequest
            from .models.order import OrderItem
            from .models.product import Product
            from .models.refund_transaction import RefundTransaction
        except Exception:
            from models.return_request import ReturnRequest
            from models.order import OrderItem
            from models.product import Product
            from models.refund_transaction import RefundTransaction

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = ReturnRequest.query.join(OrderItem, OrderItem.order_id == ReturnRequest.order_id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id)
        if q:
            like_q = f"%{q}%"
            query = query.filter((ReturnRequest.rrt_ref.ilike(like_q)) | (ReturnRequest.reason.ilike(like_q)) | (ReturnRequest.description.ilike(like_q)))
        if status_filter != 'all':
            query = query.filter(ReturnRequest.status == status_filter)

        returns = query.order_by(ReturnRequest.created_at.desc()).distinct().all()
        stats = {
            'total': len(returns),
            'pending': sum(1 for item in returns if item.status == 'pending'),
            'accepted': sum(1 for item in returns if item.status == 'accepted'),
            'refunded': sum(1 for item in returns if item.status == 'refunded'),
        }
        return render_template('seller/returns.html', returns=returns, stats=stats, filters={'q': q, 'status': status_filter})

    @app.route('/seller/returns/<rrt_ref>', methods=['POST'])
    def seller_returns_update(rrt_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.return_request import ReturnRequest
            from .models.order import OrderItem
            from .models.product import Product
            from .models.refund_transaction import RefundTransaction
        except Exception:
            from models.return_request import ReturnRequest
            from models.order import OrderItem
            from models.product import Product
            from models.refund_transaction import RefundTransaction

        return_request = ReturnRequest.query.filter_by(rrt_ref=rrt_ref).first()
        if not return_request:
            flash('Return request not found.', 'error')
            return redirect(url_for('seller_returns'))

        # ensure seller owns at least one item in the order
        seller_has_item = False
        for item in OrderItem.query.filter_by(order_id=return_request.order_id).all():
            if item.product and item.product.seller_id == current_user.id:
                seller_has_item = True
                break

        if not seller_has_item:
            flash('You do not have access to this return request.', 'error')
            return redirect(url_for('seller_returns'))

        payload_errors, payload = validate_seller_return_update_payload(request.form)
        if payload_errors:
            flash(payload_errors['action'], 'error')
            return redirect(url_for('seller_returns'))

        action = payload['action']
        notes = payload['seller_notes']
        if action == 'approve':
            return_request.status = 'accepted'
        elif action == 'deny':
            return_request.status = 'rejected'
        elif action == 'refund':
            return_request.status = 'refunded'
            existing_refund = RefundTransaction.query.filter_by(return_request_id=return_request.id).first()
            if not existing_refund:
                try:
                    from .models.order import Order
                except Exception:
                    from models.order import Order

                order = Order.query.get(return_request.order_id) if return_request.order_id else None
                seller_refund_amount = calculate_refund_amount(order, seller_id=current_user.id)
                if seller_refund_amount <= 0:
                    seller_refund_amount = float(return_request.refund_amount or 0)
                seller_refund_amount = money(seller_refund_amount)
                return_request.refund_amount = seller_refund_amount

                refund = RefundTransaction(
                    refund_ref=f"RFD-{rrt_ref}",
                    return_request_id=return_request.id,
                    amount=seller_refund_amount,
                    status='processed',
                    method='original_payment_method',
                    processed_at=datetime.utcnow(),
                )
                db.session.add(refund)
        return_request.seller_notes = notes
        return_request.resolved_at = datetime.utcnow()
        try:
            db.session.commit()
            flash(f'Return {rrt_ref} updated.', 'success')
        except Exception:
            db.session.rollback()
            flash('Could not update return request.', 'error')
        return redirect(url_for('seller_returns'))

    @app.route('/seller/return-transactions')
    @app.route('/seller/refund-transactions')
    def seller_return_transactions():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        return redirect(url_for('seller_returns'))

    @app.route('/seller/vouchers')
    def seller_vouchers():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.voucher import Voucher
        except Exception:
            from models.voucher import Voucher

        vouchers = Voucher.query.filter((Voucher.seller_id == current_user.id) | (Voucher.seller_id.is_(None))).order_by(Voucher.id.desc()).all()
        stats = {
            'active': sum(1 for row in vouchers if row.is_active),
            'redemptions_today': 0,
            'discount_total': 0.0,
            'expiring_soon': sum(1 for row in vouchers if row.valid_until and row.valid_until <= datetime.utcnow() + timedelta(days=7)),
        }
        for row in vouchers:
            stats['redemptions_today'] += int(row.uses_count or 0)
            stats['discount_total'] += float((row.discount_value or 0) * (row.uses_count or 0))
        return render_template('seller/vouchers.html', vouchers=vouchers, stats=stats)

    @app.route('/seller/analytics')
    @app.route('/seller/sales-analytics')
    def seller_analytics():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product

        rows = db.session.query(OrderItem, Product, Order).join(Product, Product.id == OrderItem.product_id).join(Order, Order.id == OrderItem.order_id).filter(Product.seller_id == current_user.id).all()

        category_revenue = {}
        top_products = {}
        total_revenue = 0.0
        order_ids = set()
        for item, product, order in rows:
            line_total = float(item.subtotal or ((item.unit_price or 0) * (item.quantity or 0)) or 0)
            total_revenue += line_total
            order_ids.add(order.id)

            category = product.category or 'Uncategorized'
            category_revenue[category] = category_revenue.get(category, 0.0) + line_total

            pkey = product.id
            if pkey not in top_products:
                top_products[pkey] = {
                    'name': product.name,
                    'units_sold': 0,
                    'revenue': 0.0,
                }
            top_products[pkey]['units_sold'] += int(item.quantity or 0)
            top_products[pkey]['revenue'] += line_total

        total_orders = len(order_ids)
        avg_order_value = (total_revenue / total_orders) if total_orders else 0.0

        categories = []
        for name, revenue in sorted(category_revenue.items(), key=lambda kv: kv[1], reverse=True):
            share = (revenue / total_revenue * 100.0) if total_revenue else 0.0
            categories.append({'name': name, 'revenue': revenue, 'share': share})

        top_products_list = sorted(top_products.values(), key=lambda row: row['revenue'], reverse=True)[:10]

        metrics = {
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'avg_order_value': avg_order_value,
            'category_count': len(categories),
        }
        return render_template('seller/analytics.html', metrics=metrics, categories=categories, top_products=top_products_list)

    def build_seller_report_rows(seller_id, days=30):
        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product
            from models.return_request import ReturnRequest

        start_date = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.session.query(Order, OrderItem, Product)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(Product.seller_id == seller_id)
            .filter(Order.created_at >= start_date)
            .all()
        )

        by_order = {}
        for order, item, product in rows:
            line_total = float(item.subtotal or ((item.unit_price or 0) * (item.quantity or 0)) or 0)
            entry = by_order.setdefault(order.id, {
                'order_ref': order.order_ref or '',
                'status': order.status or '',
                'customer_id': order.customer_id,
                'created_at': order.created_at,
                'seller_total': 0.0,
            })
            entry['seller_total'] += line_total

        report_rows = sorted(by_order.values(), key=lambda row: row['created_at'] or datetime.min, reverse=True)

        open_returns = (
            ReturnRequest.query
            .join(OrderItem, OrderItem.order_id == ReturnRequest.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(Product.seller_id == seller_id)
            .filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested']))
            .distinct()
            .count()
        )

        return report_rows, open_returns

    @app.route('/seller/reports/export/excel')
    def seller_reports_export_excel():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        from openpyxl import Workbook
        from flask import Response

        report_rows, open_returns = build_seller_report_rows(current_user.id, days=30)
        total_sales = sum(float(row['seller_total'] or 0) for row in report_rows)

        wb = Workbook()
        ws = wb.active
        ws.title = 'Seller Reports'
        ws.append(['metric', 'value'])
        ws.append(['monthly_sales', round(total_sales, 2)])
        ws.append(['order_count', len(report_rows)])
        ws.append(['open_returns', open_returns])
        ws.append([])
        ws.append(['order_ref', 'status', 'customer_id', 'seller_total', 'created_at'])
        for row in report_rows:
            ws.append([
                row['order_ref'],
                row['status'],
                row['customer_id'],
                round(float(row['seller_total'] or 0), 2),
                row['created_at'].isoformat() if row['created_at'] else '',
            ])

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return Response(
            stream.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=seller_reports.xlsx'},
        )

    @app.route('/seller/reports/export/pdf')
    def seller_reports_export_pdf():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        from flask import Response
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        report_rows, open_returns = build_seller_report_rows(current_user.id, days=30)
        total_sales = sum(float(row['seller_total'] or 0) for row in report_rows)

        stream = io.BytesIO()
        pdf = canvas.Canvas(stream, pagesize=letter)
        y = 760
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawString(50, y, 'Seller Report Summary (Last 30 Days)')
        y -= 26
        pdf.setFont('Helvetica', 11)
        pdf.drawString(50, y, f'Total Sales: PHP {total_sales:.2f}')
        y -= 18
        pdf.drawString(50, y, f'Total Orders: {len(report_rows)}')
        y -= 18
        pdf.drawString(50, y, f'Open Returns: {open_returns}')
        y -= 24
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(50, y, 'Recent Orders (Seller Share)')
        y -= 16
        pdf.setFont('Helvetica', 9)
        for row in report_rows[:25]:
            pdf.drawString(50, y, f"{row['order_ref']} | {row['status']} | PHP {float(row['seller_total'] or 0):.2f}")
            y -= 13
            if y < 50:
                pdf.showPage()
                y = 760
        pdf.save()
        stream.seek(0)

        return Response(
            stream.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=seller_reports.pdf'},
        )

    @app.route('/seller/financial-analytics')
    def seller_financial_analytics():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product
            from models.return_request import ReturnRequest

        seller_orders = db.session.query(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()

        gross_sales = sum(float(order.total or 0) for order in seller_orders)
        paid_orders = [order for order in seller_orders if order.status in ('paid', 'packed', 'shipped', 'delivered')]
        settled_orders = [order for order in seller_orders if order.status in ('delivered', 'refunded')]
        pending_settlement = sum(float(order.total or 0) for order in paid_orders if order not in settled_orders)

        seller_returns = ReturnRequest.query.join(OrderItem, OrderItem.order_id == ReturnRequest.order_id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()
        refund_exposure = sum(float(row.refund_amount or 0) for row in seller_returns if row.status in ('pending', 'accepted', 'refund_requested'))

        net_collected = sum(float(order.total or 0) for order in settled_orders)
        net_margin_rate = ((net_collected / gross_sales) * 100.0) if gross_sales else 0.0

        batches = []
        batch_map = {}
        for order in paid_orders:
            if not order.paid_at:
                continue
            day_key = order.paid_at.date().isoformat()
            batch_map[day_key] = batch_map.get(day_key, 0.0) + float(order.total or 0)
        for day_key, amount in sorted(batch_map.items(), reverse=True)[:7]:
            batches.append({'date': day_key, 'amount': amount})

        stats = {
            'gross_sales': gross_sales,
            'net_margin_rate': net_margin_rate,
            'pending_settlement': pending_settlement,
            'refund_exposure': refund_exposure,
            'batch_count': len(batches),
        }
        return render_template('seller/financial_analytics.html', stats=stats, batches=batches)

    @app.route('/seller/installment-payments')
    def seller_installment_payments():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.installment import InstallmentPlan, InstallmentSchedule
            from .models.order import Order
            from .models.product import Product
            from .models.order import OrderItem
        except Exception:
            from models.installment import InstallmentPlan, InstallmentSchedule
            from models.order import Order
            from models.product import Product
            from models.order import OrderItem

        plans = db.session.query(InstallmentPlan, Order).join(Order, Order.id == InstallmentPlan.order_id).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()
        plan_ids = [plan.id for plan, _ in plans]
        schedules = InstallmentSchedule.query.filter(InstallmentSchedule.plan_id.in_(plan_ids)).all() if plan_ids else []

        today = datetime.utcnow().date()
        due_this_week = sum(float(row.amount or 0) for row in schedules if row.due_date and today <= row.due_date <= (today + timedelta(days=7)) and row.status in ('pending', 'past_due'))
        overdue_count = sum(1 for row in schedules if row.status == 'past_due' or (row.status == 'pending' and row.due_date and row.due_date < today))
        active_plans = sum(1 for plan, _ in plans if plan.status == 'active')
        paid_count = sum(1 for row in schedules if row.status == 'paid')
        collection_rate = (paid_count / len(schedules) * 100.0) if schedules else 0.0

        timeline = []
        plan_by_id = {plan.id: (plan, order) for plan, order in plans}
        for row in sorted(schedules, key=lambda s: (s.due_date or today))[:20]:
            plan_order = plan_by_id.get(row.plan_id)
            plan = plan_order[0] if plan_order else None
            order = plan_order[1] if plan_order else None
            if row.status == 'past_due' or (row.status == 'pending' and row.due_date and row.due_date < today):
                urgency = 'overdue'
            elif row.status == 'pending':
                urgency = 'upcoming'
            else:
                urgency = 'settled'
            timeline.append({
                'schedule': row,
                'plan': plan,
                'order': order,
                'urgency': urgency,
            })

        stats = {
            'active_plans': active_plans,
            'due_this_week': due_this_week,
            'collection_rate': collection_rate,
            'overdue_count': overdue_count,
            'schedule_count': len(schedules),
        }
        return render_template('seller/installment_payments.html', stats=stats, timeline=timeline)

    @app.route('/seller/inquiries', methods=['GET'])
    @app.route('/seller/customer-inquiries')
    def seller_customer_inquiries():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.inquiry_ticket import InquiryTicket
            from .models.order import OrderItem
            from .models.product import Product
        except Exception:
            from models.inquiry_ticket import InquiryTicket
            from models.order import OrderItem
            from models.product import Product

        seller_order_ids = db.session.query(OrderItem.order_id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()
        seller_order_id_set = [row[0] for row in seller_order_ids]

        query = InquiryTicket.query.filter((InquiryTicket.assigned_to == current_user.id) | (InquiryTicket.order_id.in_(seller_order_id_set)))
        status_filter = (request.args.get('status') or 'all').strip()
        if status_filter != 'all':
            query = query.filter(InquiryTicket.status == status_filter)
        tickets = query.order_by(InquiryTicket.created_at.desc()).all()

        stats = {
            'open': sum(1 for row in tickets if row.status == 'open'),
            'in_progress': sum(1 for row in tickets if row.status == 'in_progress'),
            'resolved': sum(1 for row in tickets if row.status in ('resolved', 'closed')),
        }
        return render_template('seller/customer_inquiries.html', tickets=tickets, stats=stats, status_filter=status_filter)

    @app.route('/seller/inquiries/new', methods=['GET', 'POST'])
    def seller_inquiry_new():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.inquiry_ticket import InquiryTicket
            from .models.user import User
            from .models.order import Order
        except Exception:
            from models.inquiry_ticket import InquiryTicket
            from models.user import User
            from models.order import Order

        form_data = {
            'subject': '',
            'description': '',
            'priority': 'medium',
            'customer_email': '',
            'order_ref': '',
        }
        errors = {}

        if request.method == 'POST':
            errors, form_data = validate_inquiry_create_payload(
                request.form,
                customer_exists=lambda email: User.query.filter_by(email=email, role='customer').first() is not None,
                order_exists=lambda order_ref: Order.query.filter_by(order_ref=order_ref).first() is not None,
            )
            customer_email = form_data['customer_email']
            order_ref = form_data['order_ref']
            customer = User.query.filter_by(email=customer_email, role='customer').first() if customer_email else None
            order = Order.query.filter_by(order_ref=order_ref).first() if order_ref else None
            if errors:
                return render_template('seller/inquiry_form.html', errors=errors, form=form_data)

            ticket_ref = f"INQ-{datetime.utcnow().strftime('%y%m%d%H%M%S')}-{current_user.id}"
            ticket = InquiryTicket(
                ticket_ref=ticket_ref,
                customer_id=customer.id,
                order_id=order.id if order else None,
                assigned_to=current_user.id,
                subject=form_data['subject'],
                description=form_data['description'],
                priority=form_data['priority'],
                status='open',
            )
            try:
                db.session.add(ticket)
                db.session.commit()
                flash(f'Ticket {ticket_ref} created.', 'success')
                return redirect(url_for('seller_customer_inquiries'))
            except Exception:
                db.session.rollback()
                errors = {'general': 'Could not create inquiry ticket.'}
                return render_template('seller/inquiry_form.html', errors=errors, form=form_data)

        return render_template('seller/inquiry_form.html', errors=errors, form=form_data)

    @app.route('/seller/inquiries/<ticket_ref>', methods=['GET', 'POST'])
    def seller_inquiry_detail(ticket_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.inquiry_ticket import InquiryTicket
        except Exception:
            from models.inquiry_ticket import InquiryTicket

        ticket = InquiryTicket.query.filter_by(ticket_ref=ticket_ref).first()
        if not ticket:
            flash('Inquiry not found.', 'error')
            return redirect(url_for('seller_customer_inquiries'))

        if request.method == 'POST':
            payload_errors, payload = validate_inquiry_update_payload(request.form)
            if payload_errors:
                return render_template('seller/inquiry_detail.html', ticket=ticket, errors=payload_errors, form=payload)

            next_status = payload['status']
            note = payload['description']
            ticket.status = next_status
            ticket.description = note
            ticket.assigned_to = current_user.id
            if next_status in ('resolved', 'closed') and not ticket.resolved_at:
                ticket.resolved_at = datetime.utcnow()
            try:
                db.session.commit()
                flash(f'Inquiry {ticket_ref} updated.', 'success')
            except Exception:
                db.session.rollback()
                payload_errors = {'general': 'Could not update inquiry.'}
                return render_template('seller/inquiry_detail.html', ticket=ticket, errors=payload_errors, form=payload)
            return redirect(url_for('seller_inquiry_detail', ticket_ref=ticket_ref))

        return render_template('seller/inquiry_detail.html', ticket=ticket, errors={}, form={'status': ticket.status, 'description': ticket.description})

    @app.route('/seller/customer-accounts')
    def seller_customer_accounts():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
            from .models.user import User
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product
            from models.user import User

        rows = db.session.query(Order, User).join(User, User.id == Order.customer_id).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).all()
        by_customer = {}
        for order, user in rows:
            key = user.id
            item = by_customer.setdefault(key, {
                'user': user,
                'orders': 0,
                'ltv': 0.0,
                'last_order': None,
                'order_ids': set(),
            })
            if order.id not in item['order_ids']:
                item['order_ids'].add(order.id)
                item['orders'] += 1
                item['ltv'] += float(order.total or 0)
            if not item['last_order'] or (order.created_at and order.created_at > item['last_order']):
                item['last_order'] = order.created_at

        accounts = []
        for row in by_customer.values():
            row.pop('order_ids', None)
            accounts.append(row)
        accounts.sort(key=lambda row: row['ltv'], reverse=True)
        stats = {
            'total_accounts': len(accounts),
            'vip': sum(1 for row in accounts if row['ltv'] >= 50000),
            'at_risk': sum(1 for row in accounts if row['last_order'] and row['last_order'] < datetime.utcnow() - timedelta(days=60)),
            'avg_ltv': (sum(row['ltv'] for row in accounts) / len(accounts)) if accounts else 0.0,
        }
        return render_template('seller/customer_accounts.html', accounts=accounts, stats=stats)

    @app.route('/seller/retention-engagement')
    @app.route('/seller/crm-analytics')
    def seller_crm_analytics():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
            from .models.voucher import Voucher
            from .models.inquiry_ticket import InquiryTicket
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product
            from models.voucher import Voucher
            from models.inquiry_ticket import InquiryTicket

        seller_orders = db.session.query(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()
        customer_counts = {}
        for row in seller_orders:
            customer_counts[row.customer_id] = customer_counts.get(row.customer_id, 0) + 1

        customer_total = len(customer_counts)
        repeat_customers = sum(1 for count in customer_counts.values() if count > 1)
        repeat_rate = (repeat_customers / customer_total * 100.0) if customer_total else 0.0
        retention_90 = (sum(1 for row in seller_orders if row.created_at and row.created_at >= datetime.utcnow() - timedelta(days=90)) / len(seller_orders) * 100.0) if seller_orders else 0.0

        voucher_usage = int(sum(int(v.uses_count or 0) for v in Voucher.query.filter((Voucher.seller_id == current_user.id) | (Voucher.seller_id.is_(None))).all()))
        inquiries = InquiryTicket.query.filter_by(assigned_to=current_user.id).all()
        inquiry_to_sale = (len([i for i in inquiries if i.status in ('resolved', 'closed')]) / len(inquiries) * 100.0) if inquiries else 0.0
        churn_risk = (sum(1 for count in customer_counts.values() if count == 1) / customer_total * 100.0) if customer_total else 0.0

        metrics = {
            'retention_90': retention_90,
            'repeat_rate': repeat_rate,
            'inquiry_to_sale': inquiry_to_sale,
            'churn_risk': churn_risk,
            'voucher_usage': voucher_usage,
            'customer_total': customer_total,
        }
        return render_template('seller/crm_analytics.html', metrics=metrics)

    @app.route('/seller/invoices')
    def seller_invoices():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.invoice import Invoice
        except Exception:
            from models.invoice import Invoice
        invoices = Invoice.query.filter_by(seller_id=current_user.id).order_by(Invoice.issued_at.desc()).all()
        return render_template('seller/invoices.html', invoices=invoices)

    @app.route('/seller/invoices/<invoice_ref>')
    def seller_invoice_detail(invoice_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.invoice import Invoice
        except Exception:
            from models.invoice import Invoice
        invoice = Invoice.query.filter_by(invoice_ref=invoice_ref, seller_id=current_user.id).first()
        if not invoice:
            flash('Invoice not found.', 'error')
            return redirect(url_for('seller_invoices'))
        return render_template('seller/invoice_detail.html', invoice=invoice)

    @app.route('/seller/inventory-analytics')
    def seller_inventory_analytics():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
            from .models.order import OrderItem
        except Exception:
            from models.product import Product
            from models.order import OrderItem

        products = Product.query.filter_by(seller_id=current_user.id).all()
        sold_by_product = {}
        sold_rows = db.session.query(OrderItem.product_id, db.func.sum(OrderItem.quantity)).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).group_by(OrderItem.product_id).all()
        for pid, qty in sold_rows:
            sold_by_product[pid] = int(qty or 0)

        total_sold = sum(sold_by_product.values())
        total_stock = sum(int(product.stock or 0) for product in products)
        sell_through_rate = (total_sold / (total_sold + total_stock) * 100.0) if (total_sold + total_stock) else 0.0
        aging_skus = sum(1 for product in products if product.created_at and product.created_at < (datetime.utcnow() - timedelta(days=90)) and (product.stock or 0) > 0)
        stockout_incidents = sum(1 for product in products if (product.stock or 0) <= 0)

        ranked = []
        for product in products:
            sold = sold_by_product.get(product.id, 0)
            on_hand = int(product.stock or 0)
            velocity = sold
            ranked.append({'product': product, 'velocity': velocity, 'on_hand': on_hand})
        ranked.sort(key=lambda row: row['velocity'], reverse=True)

        stats = {
            'sell_through_rate': sell_through_rate,
            'aging_skus': aging_skus,
            'stockout_incidents': stockout_incidents,
            'lead_time_avg': 0,
        }
        return render_template('seller/inventory_analytics.html', stats=stats, fast_movers=ranked[:5], slow_movers=list(reversed(ranked[-5:] if ranked else [])))

    @app.route('/seller/delivery-services')
    def seller_delivery_services():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product

        orders = db.session.query(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()
        in_transit = sum(1 for order in orders if order.status == 'shipped')
        delivered = [order for order in orders if order.status == 'delivered']
        failed = sum(1 for order in orders if order.status == 'cancelled')
        on_time = 0
        for order in delivered:
            if order.shipped_at and order.delivered_at and (order.delivered_at - order.shipped_at).days <= 3:
                on_time += 1
        on_time_rate = (on_time / len(delivered) * 100.0) if delivered else 0.0

        stats = {
            'in_transit': in_transit,
            'on_time_rate': on_time_rate,
            'failed_attempts': failed,
            'avg_delivery_days': ((sum((order.delivered_at - order.shipped_at).total_seconds() for order in delivered if order.shipped_at and order.delivered_at) / 86400.0) / len(delivered)) if delivered else 0.0,
        }
        recent_shipments = sorted([order for order in orders if order.status in ('shipped', 'delivered', 'cancelled')], key=lambda row: row.created_at or datetime.utcnow(), reverse=True)[:10]
        return render_template('seller/delivery_services.html', stats=stats, recent_shipments=recent_shipments)

    @app.route('/seller/vouchers/create', methods=['GET', 'POST'])
    def seller_voucher_create():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.voucher import Voucher
        except Exception:
            from models.voucher import Voucher

        if request.method == 'POST':
            import re
            code = (request.form.get('code') or '').strip().upper()
            discount_type = (request.form.get('discount_type') or 'percent').strip()
            is_active = bool(request.form.get('is_active'))

            try:
                discount_value = float(request.form.get('discount_value') or 0)
            except Exception:
                discount_value = -1
            try:
                min_order_amount = float(request.form.get('min_order_amount') or 0)
            except Exception:
                min_order_amount = -1
            try:
                max_uses_raw = (request.form.get('max_uses') or '').strip()
                max_uses = int(max_uses_raw) if max_uses_raw else None
            except Exception:
                max_uses = -1
            try:
                per_user_limit_raw = (request.form.get('per_user_limit') or '').strip()
                per_user_limit = int(per_user_limit_raw) if per_user_limit_raw else 1
            except Exception:
                per_user_limit = -1

            valid_from = None
            valid_until = None
            valid_from_raw = (request.form.get('valid_from') or '').strip()
            valid_until_raw = (request.form.get('valid_until') or '').strip()
            try:
                if valid_from_raw:
                    valid_from = datetime.strptime(valid_from_raw, '%Y-%m-%dT%H:%M')
                if valid_until_raw:
                    valid_until = datetime.strptime(valid_until_raw, '%Y-%m-%dT%H:%M')
            except Exception:
                valid_from = '__invalid__'

            errors = []
            if not code or not re.match(r'^[A-Z0-9_-]{4,30}$', code):
                errors.append('Voucher code must be 4-30 chars using A-Z, 0-9, dash, or underscore.')
            if Voucher.query.filter(Voucher.code.ilike(code)).first():
                errors.append('Voucher code already exists.')
            if discount_type not in ('percent', 'fixed'):
                errors.append('Invalid discount type.')
            if discount_value <= 0:
                errors.append('Discount value must be greater than 0.')
            if discount_type == 'percent' and discount_value > 100:
                errors.append('Percent discount cannot exceed 100.')
            if min_order_amount < 0:
                errors.append('Minimum order amount cannot be negative.')
            if max_uses is not None and max_uses <= 0:
                errors.append('Max uses must be greater than 0 when set.')
            if per_user_limit is not None and per_user_limit <= 0:
                errors.append('Per-user limit must be greater than 0 when set.')
            if valid_from == '__invalid__':
                errors.append('Invalid validity date format.')
            elif valid_from and valid_until and valid_until <= valid_from:
                errors.append('Valid until must be later than valid from.')

            if errors:
                for message in errors:
                    flash(message, 'error')
                return render_template('seller/vouchers.html', create_mode=True, form=request.form)

            voucher_ref = f"VCH-S{current_user.id}-{datetime.utcnow().strftime('%y%m%d%H%M%S')}"
            try:
                db.session.add(Voucher(
                    voucher_ref=voucher_ref,
                    code=code,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    min_order_amount=min_order_amount,
                    max_uses=max_uses,
                    uses_count=0,
                    per_user_limit=per_user_limit,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    seller_id=current_user.id,
                    is_active=is_active,
                    combinable=False,
                ))
                db.session.commit()
                flash(f'Voucher {code} created.', 'success')
                return redirect(url_for('seller_vouchers'))
            except Exception:
                db.session.rollback()
                flash('Could not create voucher right now.', 'error')

        return render_template('seller/vouchers.html', create_mode=True, form={})

    @app.route('/seller/payouts')
    def seller_payouts():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order, OrderItem
            from .models.product import Product
        except Exception:
            from models.order import Order, OrderItem
            from models.product import Product

        orders = db.session.query(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct().all()
        available_balance = sum(float(order.total or 0) for order in orders if order.status == 'delivered')
        pending_clearance = sum(float(order.total or 0) for order in orders if order.status in ('paid', 'packed', 'shipped'))

        today = datetime.utcnow().date()
        days_to_friday = (4 - today.weekday()) % 7
        next_transfer = today + timedelta(days=days_to_friday)

        stats = {
            'available_balance': available_balance,
            'pending_clearance': pending_clearance,
            'next_transfer': next_transfer,
            'payout_count': len([order for order in orders if order.status == 'delivered']),
        }
        history = sorted([order for order in orders if order.status in ('delivered', 'refunded')], key=lambda row: row.delivered_at or row.created_at or datetime.utcnow(), reverse=True)[:8]
        return render_template('seller/payouts.html', stats=stats, history=history)

    @app.route('/seller/settings')
    def seller_settings():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        settings_cards = [
            {
                'title': 'Business Profile',
                'description': 'Manage business identity, contact details, and address data.',
                'href': '/seller/profile',
                'status': 'available',
            },
            {
                'title': 'Security',
                'description': 'Update account credentials and strengthen seller account protection.',
                'href': '/seller/security',
                'status': 'available',
            },
            {
                'title': 'Payouts',
                'description': 'Track settlement balances and payout transfer schedules.',
                'href': '/seller/payouts',
                'status': 'available',
            },
        ]
        return render_template('seller/settings.html', settings_cards=settings_cards)

    @app.route('/seller/profile', methods=['GET', 'POST'])
    def seller_profile():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        if request.method == 'POST':
            profile_errors, profile_data = validate_seller_profile_payload(request.form, postal_lookup)
            if profile_errors:
                return render_template('seller/profile.html', seller=current_user, errors=profile_errors, form=profile_data)

            current_user.business_name = profile_data['business_name']
            current_user.full_name = profile_data['full_name']
            current_user.phone = profile_data['phone'] or None
            current_user.address_line1 = profile_data['address_line1'] or None
            current_user.address_line2 = profile_data['address_line2'] or None
            current_user.barangay = profile_data['barangay'] or None
            current_user.city_municipality = profile_data['city_municipality'] or None
            current_user.province = profile_data['province'] or None
            current_user.region = profile_data['region'] or None
            current_user.postal_code = profile_data['postal_code'] or None
            try:
                db.session.commit()
                flash('Business profile updated.', 'success')
            except Exception:
                db.session.rollback()
                profile_errors = {'general': 'Could not update profile right now.'}
                return render_template('seller/profile.html', seller=current_user, errors=profile_errors, form=profile_data)
            return redirect(url_for('seller_profile'))

        profile_data = {
            'business_name': current_user.business_name or '',
            'full_name': current_user.full_name or '',
            'phone': current_user.phone or '',
            'address_line1': current_user.address_line1 or '',
            'address_line2': current_user.address_line2 or '',
            'barangay': current_user.barangay or '',
            'city_municipality': current_user.city_municipality or '',
            'province': current_user.province or '',
            'region': current_user.region or '',
            'postal_code': current_user.postal_code or '',
        }
        return render_template('seller/profile.html', seller=current_user, errors={}, form=profile_data)

    @app.route('/seller/security', methods=['GET', 'POST'])
    def seller_security():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        form_data = {
            'current_password': '',
            'new_password': '',
            'confirm_password': '',
        }
        errors = {}

        if request.method == 'POST':
            errors, form_data = validate_seller_security_payload(
                request.form,
                check_current_password=lambda provided: current_user.check_password(provided),
            )
            if errors:
                return render_template('seller/security.html', errors=errors, form=form_data)

            try:
                current_user.set_password(form_data['new_password'])
                db.session.commit()
                flash('Password updated.', 'success')
            except Exception:
                db.session.rollback()
                errors = {'general': 'Could not update password right now.'}
                return render_template('seller/security.html', errors=errors, form=form_data)
            return redirect(url_for('seller_security'))

        return render_template('seller/security.html', errors=errors, form=form_data)

    @app.route('/admin/dashboard')
    def admin_dashboard():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.product import Product
            from .models.return_request import ReturnRequest
            from .models.audit import AuditLog
        except Exception:
            from models.order import Order
            from models.product import Product
            from models.return_request import ReturnRequest
            from models.audit import AuditLog

        now = datetime.utcnow()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_week = start_today - timedelta(days=6)

        def sum_order_totals(rows):
            total = 0.0
            for row in rows:
                try:
                    total += float(row.total or 0)
                except Exception:
                    total += 0.0
            return total

        todays_orders = Order.query.filter(Order.created_at >= start_today).all()
        gmv_today = sum_order_totals(todays_orders)

        active_sellers = User.query.filter(User.role == 'seller', User.is_active.is_(True)).count()
        pending_sellers = User.query.filter(User.role == 'seller', User.seller_verification_status == 'pending').count()

        system_errors = AuditLog.query.filter(AuditLog.created_at >= start_today, AuditLog.action.ilike('%fail%')).count()
        open_returns = ReturnRequest.query.filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested'])).count()

        sales_points = []
        for day_offset in range(6, -1, -1):
            day_start = start_today - timedelta(days=day_offset)
            day_end = day_start + timedelta(days=1)
            day_total = sum_order_totals(Order.query.filter(Order.created_at >= day_start, Order.created_at < day_end).all())
            sales_points.append({'label': day_start.strftime('%a'), 'value': day_total})

        recent_security = AuditLog.query.filter(
            AuditLog.created_at >= start_week,
            (AuditLog.module.ilike('%security%')) | (AuditLog.action.ilike('%login%')) | (AuditLog.action.ilike('%lock%'))
        ).order_by(AuditLog.created_at.desc()).limit(3).all()

        alerts = []
        if pending_sellers > 0:
            alerts.append({'title': 'Pending Seller Verification', 'message': f'{pending_sellers} seller account(s) waiting for review.', 'time': 'now'})
        if open_returns > 0:
            alerts.append({'title': 'Open Return/Refund Cases', 'message': f'{open_returns} return case(s) need admin visibility.', 'time': 'today'})
        for row in recent_security:
            alerts.append({
                'title': (row.action or 'Security Event').replace('_', ' ').title(),
                'message': row.target_ref or row.module or 'Security-related activity detected.',
                'time': row.created_at.strftime('%b %d, %H:%M') if row.created_at else '-',
            })

        if not alerts:
            alerts.append({'title': 'No Critical Alerts', 'message': 'All monitored systems are currently stable.', 'time': '-'})

        stats = {
            'gmv_today': gmv_today,
            'active_sellers': active_sellers,
            'system_errors': system_errors,
            'compliance_alerts': pending_sellers + open_returns,
        }

        return render_template('admin/dashboard.html', stats=stats, sales_points=sales_points, alerts=alerts)

    @app.route('/admin/sellers', methods=['GET', 'POST'])
    def admin_sellers():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
            from .models.audit import AuditLog
        except Exception:
            from models.product import Product
            from models.audit import AuditLog

        def write_audit(action, target_ref, meta=None):
            try:
                db.session.add(AuditLog(
                    actor_id=current_user.id,
                    actor_name=getattr(current_user, 'full_name', None) or current_user.email,
                    role='admin',
                    action=action,
                    module='seller_management',
                    target_ref=target_ref,
                    meta=meta or {},
                    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            seller_id = request.form.get('seller_id', type=int)
            seller = User.query.filter_by(id=seller_id, role='seller').first() if seller_id else None
            if not seller:
                flash('Seller not found.', 'error')
            else:
                try:
                    if action == 'approve':
                        seller.seller_verification_status = 'approved'
                        seller.is_active = True
                        db.session.commit()
                        write_audit('approve_seller', seller.email, {'seller_id': seller.id})
                        flash(f'Approved {seller.email}.', 'success')
                    elif action == 'reject':
                        seller.seller_verification_status = 'rejected'
                        seller.is_active = False
                        db.session.commit()
                        write_audit('reject_seller', seller.email, {'seller_id': seller.id})
                        flash(f'Rejected {seller.email}.', 'warning')
                    elif action == 'toggle_active':
                        seller.is_active = not bool(seller.is_active)
                        db.session.commit()
                        write_audit('toggle_seller_active', seller.email, {'seller_id': seller.id, 'is_active': bool(seller.is_active)})
                        flash(f'Updated status for {seller.email}.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not update seller status right now.', 'error')
            return redirect(url_for('admin_sellers', q=request.args.get('q', ''), status=request.args.get('status', 'all')))

        try:
            from .models.product import Product
            from .models.order import Order
        except Exception:
            from models.product import Product
            from models.order import Order

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip().lower()

        query = User.query.filter(User.role == 'seller')
        if q:
            like_q = f"%{q}%"
            query = query.filter((User.email.ilike(like_q)) | (User.business_name.ilike(like_q)) | (User.full_name.ilike(like_q)))
        if status_filter in ('pending', 'approved', 'rejected'):
            query = query.filter(User.seller_verification_status == status_filter)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active.is_(False))

        sellers = query.order_by(User.created_at.desc()).all()
        product_count_by_seller = {}
        for row in Product.query.all():
            product_count_by_seller[row.seller_id] = int(product_count_by_seller.get(row.seller_id, 0)) + 1

        rows = []
        for seller in sellers:
            rows.append({
                'seller': seller,
                'product_count': int(product_count_by_seller.get(seller.id, 0)),
                'status': (seller.seller_verification_status or 'pending').lower(),
            })

        total_gmv = sum(float(o.total or 0) for o in Order.query.filter(Order.status.in_(['paid', 'packed', 'shipped', 'delivered'])).all())
        stats = {
            'verified': User.query.filter(User.role == 'seller', User.seller_verification_status == 'approved').count(),
            'pending': User.query.filter(User.role == 'seller', User.seller_verification_status == 'pending').count(),
            'suspended': User.query.filter(User.role == 'seller', User.is_active.is_(False)).count(),
            'gmv_share': total_gmv,
        }

        return render_template('admin/sellers.html', sellers=rows, stats=stats, filters={'q': q, 'status': status_filter})

    @app.route('/admin/permits/<path:filename>')
    def admin_view_permit(filename):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return abort(403)
        
        from flask import send_from_directory
        directory = os.path.join(app.instance_path, 'uploads', 'permits')
        return send_from_directory(directory, filename)

    @app.route('/admin/sellers/<seller_id>')
    def admin_seller_detail(seller_id):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
            from .models.order import Order, OrderItem
            from .models.return_request import ReturnRequest
            from .models.audit import AuditLog
        except Exception:
            from models.product import Product
            from models.order import Order, OrderItem
            from models.return_request import ReturnRequest
            from models.audit import AuditLog

        seller = User.query.filter((User.id == seller_id) | (User.seller_code == seller_id) | (User.email == seller_id)).filter(User.role == 'seller').first()
        if not seller:
            flash('Seller not found.', 'error')
            return redirect(url_for('admin_sellers'))

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            try:
                if action == 'approve':
                    seller.seller_verification_status = 'approved'
                    seller.is_active = True
                    db.session.commit()
                    flash(f'Approved {seller.email}.', 'success')
                elif action == 'reject':
                    seller.seller_verification_status = 'rejected'
                    seller.is_active = False
                    db.session.commit()
                    flash(f'Rejected {seller.email}.', 'warning')
            except Exception:
                db.session.rollback()
                flash('Could not update seller status.', 'error')
            return redirect(url_for('admin_seller_detail', seller_id=seller.id))

        products = Product.query.filter_by(seller_id=seller.id).all()
        product_ids = [p.id for p in products]
        order_ids = set()
        if product_ids:
            for item in OrderItem.query.filter(OrderItem.product_id.in_(product_ids)).all():
                if item.order_id:
                    order_ids.add(item.order_id)

        orders = Order.query.filter(Order.id.in_(list(order_ids))).all() if order_ids else []
        order_refs = [o.order_ref for o in orders if o.order_ref]
        returns_count = ReturnRequest.query.filter(ReturnRequest.order_id.in_([o.id for o in orders])).count() if orders else 0

        payout_total = 0.0
        for order in orders:
            if order.status in ('delivered', 'paid', 'shipped', 'packed'):
                try:
                    payout_total += float(order.total or 0)
                except Exception:
                    payout_total += 0.0

        recent_actions = AuditLog.query.filter(
            (AuditLog.target_ref == seller.email) | (AuditLog.target_ref == seller.seller_code)
        ).order_by(AuditLog.created_at.desc()).limit(5).all()

        metrics = {
            'products': len(products),
            'orders': len(orders),
            'returns': int(returns_count),
            'payout_total': payout_total,
        }

        return render_template(
            'admin/seller_detail.html',
            seller=seller,
            metrics=metrics,
            recent_products=products[:5],
            recent_actions=recent_actions,
            order_refs=order_refs[:5],
        )

    @app.route('/admin/audit')
    def admin_audit():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.audit import AuditLog
        except Exception:
            from models.audit import AuditLog

        q = (request.args.get('q') or '').strip()
        action_filter = (request.args.get('action') or 'all').strip().lower()
        module_filter = (request.args.get('module') or 'all').strip().lower()

        query = AuditLog.query
        if q:
            like_q = f"%{q}%"
            query = query.filter(
                (AuditLog.actor_name.ilike(like_q))
                | (AuditLog.target_ref.ilike(like_q))
                | (AuditLog.action.ilike(like_q))
                | (AuditLog.module.ilike(like_q))
            )
        if action_filter != 'all':
            query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
        if module_filter != 'all':
            query = query.filter(AuditLog.module.ilike(f"%{module_filter}%"))

        logs = query.order_by(AuditLog.created_at.desc()).limit(200).all()

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = {
            'actions_today': AuditLog.query.filter(AuditLog.created_at >= today_start).count(),
            'security_events': AuditLog.query.filter(AuditLog.created_at >= today_start, AuditLog.module.ilike('%security%')).count(),
            'admin_changes': AuditLog.query.filter(AuditLog.created_at >= today_start, AuditLog.role == 'admin').count(),
            'reveal_actions': AuditLog.query.filter(AuditLog.created_at >= today_start, AuditLog.action.ilike('%reveal%')).count(),
        }

        return render_template('admin/audit.html', logs=logs, stats=stats, filters={'q': q, 'action': action_filter, 'module': module_filter})

    @app.route('/admin/products', methods=['GET', 'POST'])
    def admin_products():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            product_id = request.form.get('product_id', type=int)
            product = Product.query.get(product_id) if product_id else None

            if not product:
                flash('Product not found.', 'error')
            elif action == 'update':
                try:
                    price_val = request.form.get('price')
                    stock_val = request.form.get('stock')
                    is_active = (request.form.get('is_active') or '1').strip() == '1'
                    if price_val is not None and str(price_val).strip() != '':
                        product.price = float(price_val)
                    if stock_val is not None and str(stock_val).strip() != '':
                        product.stock = int(stock_val)
                    product.is_active = is_active
                    db.session.commit()
                    flash(f'Updated {product.product_ref}.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not update product.', 'error')
            elif action == 'delete':
                try:
                    ref = product.product_ref
                    db.session.delete(product)
                    db.session.commit()
                    flash(f'Deleted {ref}.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not delete product. It may be linked to existing orders.', 'error')

            return redirect(url_for('admin_products', q=request.args.get('q', ''), status=request.args.get('status', 'all')))

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = Product.query
        if q:
            like_q = f"%{q}%"
            query = query.filter(
                (Product.product_ref.ilike(like_q))
                | (Product.name.ilike(like_q))
                | (Product.category.ilike(like_q))
            )
        if status_filter == 'active':
            query = query.filter(Product.is_active.is_(True))
        elif status_filter == 'inactive':
            query = query.filter(Product.is_active.is_(False))
        elif status_filter == 'low_stock':
            query = query.filter(Product.stock <= Product.low_stock_threshold)

        products = query.order_by(Product.created_at.desc()).all()

        stats = {
            'total': Product.query.count(),
            'active': Product.query.filter(Product.is_active.is_(True)).count(),
            'low_stock': Product.query.filter(Product.stock <= Product.low_stock_threshold).count(),
        }

        return render_template(
            'admin/products.html',
            products=products,
            stats=stats,
            filters={'q': q, 'status': status_filter},
        )

    @app.route('/admin/products/export')
    def admin_products_export():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        q = (request.args.get('q') or '').strip()
        status_filter = (request.args.get('status') or 'all').strip()
        query = Product.query
        if q:
            like_q = f"%{q}%"
            query = query.filter(
                (Product.product_ref.ilike(like_q))
                | (Product.name.ilike(like_q))
                | (Product.category.ilike(like_q))
            )
        if status_filter == 'active':
            query = query.filter(Product.is_active.is_(True))
        elif status_filter == 'inactive':
            query = query.filter(Product.is_active.is_(False))
        elif status_filter == 'low_stock':
            query = query.filter(Product.stock <= Product.low_stock_threshold)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['id', 'product_ref', 'name', 'category', 'seller_id', 'price', 'stock', 'status'])
        for row in query.order_by(Product.created_at.desc()).all():
            writer.writerow([
                row.id,
                row.product_ref,
                row.name,
                row.category or '',
                row.seller_id,
                f"{float(row.price or 0):.2f}",
                row.stock,
                'active' if row.is_active else 'inactive',
            ])

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=admin_products_export.csv'},
        )

    @app.route('/admin/customers', methods=['GET', 'POST'])
    def admin_customers():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.audit import AuditLog
        except Exception:
            try:
                from models.audit import AuditLog
            except Exception:
                AuditLog = None

        def write_audit(action, target_ref, meta=None):
            if AuditLog is None:
                return
            try:
                log = AuditLog(
                    actor_id=current_user.id,
                    actor_name=getattr(current_user, 'full_name', None) or current_user.email,
                    role='admin',
                    action=action,
                    module='user_management',
                    target_ref=target_ref,
                    meta=meta or {},
                    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                )
                db.session.add(log)
                db.session.commit()
            except Exception:
                db.session.rollback()

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            if action == 'create':
                email = (request.form.get('email') or '').strip().lower()
                full_name = (request.form.get('full_name') or '').strip()
                role = (request.form.get('role') or 'customer').strip()
                password = request.form.get('password') or ''
                errors = []
                if not email or '@' not in email:
                    errors.append('A valid email is required.')
                if not full_name or len(full_name) < 2:
                    errors.append('Full name must be at least 2 characters.')
                if role not in ('customer', 'seller', 'admin'):
                    errors.append('Role is invalid.')
                if len(password) < 8:
                    errors.append('Password must be at least 8 characters.')
                if User.query.filter_by(email=email).first():
                    errors.append('Email is already in use.')

                if errors:
                    flash(' '.join(errors), 'error')
                else:
                    try:
                        user = User(email=email, full_name=full_name, role=role, is_active=True)
                        user.set_password(password)
                        db.session.add(user)
                        db.session.commit()
                        write_audit('create_user', email, {'role': role})
                        flash(f'User {email} created.', 'success')
                    except Exception:
                        db.session.rollback()
                        flash('Could not create user. Please try again.', 'error')

            elif action == 'update':
                user_id = request.form.get('user_id', type=int)
                if user_id:
                    user = User.query.get(user_id)
                else:
                    user = None
                if not user:
                    flash('User not found.', 'error')
                elif user.id == current_user.id and request.form.get('is_active') == '0':
                    flash('You cannot deactivate your own admin account.', 'error')
                else:
                    role = (request.form.get('role') or user.role).strip()
                    is_active = (request.form.get('is_active') or '1').strip() == '1'
                    full_name = (request.form.get('full_name') or user.full_name or '').strip()
                    if role not in ('customer', 'seller', 'admin'):
                        flash('Role is invalid.', 'error')
                    else:
                        try:
                            old_role = user.role
                            old_active = user.is_active
                            user.role = role
                            user.is_active = is_active
                            user.full_name = full_name
                            db.session.commit()
                            write_audit(
                                'update_user',
                                user.email,
                                {
                                    'old_role': old_role,
                                    'new_role': role,
                                    'old_active': bool(old_active),
                                    'new_active': bool(is_active),
                                },
                            )
                            flash(f'Updated {user.email}.', 'success')
                        except Exception:
                            db.session.rollback()
                            flash('Could not update user.', 'error')

            elif action == 'delete':
                user_id = request.form.get('user_id', type=int)
                if user_id:
                    user = User.query.get(user_id)
                else:
                    user = None
                if not user:
                    flash('User not found.', 'error')
                elif user.id == current_user.id:
                    flash('You cannot delete your own admin account.', 'error')
                else:
                    try:
                        email = user.email
                        db.session.delete(user)
                        db.session.commit()
                        write_audit('delete_user', email)
                        flash(f'Deleted {email}.', 'success')
                    except Exception:
                        db.session.rollback()
                        flash('Could not delete user. Ensure related records are handled first.', 'error')

            return redirect(url_for('admin_customers', q=request.args.get('q', ''), role=request.args.get('role', 'all'), status=request.args.get('status', 'all')))

        q = (request.args.get('q') or '').strip()
        role_filter = (request.args.get('role') or 'all').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = User.query
        if q:
            like_q = f"%{q}%"
            query = query.filter((User.email.ilike(like_q)) | (User.full_name.ilike(like_q)))
        if role_filter in ('customer', 'seller', 'admin'):
            query = query.filter(User.role == role_filter)
        if status_filter == 'active':
            query = query.filter(User.is_active.is_(True))
        elif status_filter == 'inactive':
            query = query.filter(User.is_active.is_(False))

        users = query.order_by(User.created_at.desc()).all()
        stats = {
            'total': User.query.count(),
            'active': User.query.filter(User.is_active.is_(True)).count(),
            'customers': User.query.filter(User.role == 'customer').count(),
            'sellers': User.query.filter(User.role == 'seller').count(),
            'admins': User.query.filter(User.role == 'admin').count(),
        }
        return render_template(
            'admin/customers.html',
            users=users,
            stats=stats,
            filters={'q': q, 'role': role_filter, 'status': status_filter},
        )

    @app.route('/admin/customers/export')
    def admin_customers_export():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        q = (request.args.get('q') or '').strip()
        role_filter = (request.args.get('role') or 'all').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = User.query
        if q:
            like_q = f"%{q}%"
            query = query.filter((User.email.ilike(like_q)) | (User.full_name.ilike(like_q)))
        if role_filter in ('customer', 'seller', 'admin'):
            query = query.filter(User.role == role_filter)
        if status_filter == 'active':
            query = query.filter(User.is_active.is_(True))
        elif status_filter == 'inactive':
            query = query.filter(User.is_active.is_(False))

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['id', 'full_name', 'email', 'role', 'status', 'created_at'])
        for user in query.order_by(User.created_at.desc()).all():
            writer.writerow([
                user.id,
                user.full_name or '',
                user.email,
                user.role,
                'active' if user.is_active else 'inactive',
                user.created_at.isoformat() if user.created_at else '',
            ])
        csv_data = output.getvalue()
        output.close()

        from flask import Response
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=admin_users_export.csv'},
        )

    @app.route('/admin/settings')
    def admin_settings():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.audit import AuditLog
        except Exception:
            from models.audit import AuditLog

        latest_backup_event = AuditLog.query.filter(
            (AuditLog.action.ilike('%backup%')) | (AuditLog.module.ilike('%backup%'))
        ).order_by(AuditLog.created_at.desc()).first()

        settings_state = {
            'platform_name': 'E-ACIS',
            'maintenance_mode': 'Disabled (Live)',
            'admin_timeout_minutes': 15,
            'audit_retention_days': 365,
            'backup_frequency': 'Daily',
            'latest_backup': latest_backup_event.created_at.strftime('%Y-%m-%d %H:%M') if latest_backup_event and latest_backup_event.created_at else 'No recorded backup event',
        }

        return render_template('admin/settings.html', settings_state=settings_state)

    @app.route('/admin/reports')
    def admin_reports():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        now = datetime.utcnow()
        start_day = now - timedelta(days=1)
        start_week = now - timedelta(days=7)
        start_month = now - timedelta(days=30)

        def order_total_since(dt):
            total = 0.0
            rows = Order.query.filter(Order.created_at >= dt).all()
            for row in rows:
                try:
                    total += float(row.total or 0)
                except Exception:
                    total += 0.0
            return total

        sales = {
            'daily': order_total_since(start_day),
            'weekly': order_total_since(start_week),
            'monthly': order_total_since(start_month),
        }

        open_returns = ReturnRequest.query.filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested'])).count()

        reasons = ['Late Delivery', 'Damaged Item', 'Wrong Item']
        complaints = []
        for reason in reasons:
            lower_reason = reason.lower()
            count_24h = ReturnRequest.query.filter(ReturnRequest.created_at >= start_day, ReturnRequest.reason.ilike(f"%{lower_reason}%")).count()
            count_7d = ReturnRequest.query.filter(ReturnRequest.created_at >= start_week, ReturnRequest.reason.ilike(f"%{lower_reason}%")).count()
            status = 'Elevated' if count_24h >= 5 else 'Stable'
            complaints.append({'category': reason, 'last_24h': count_24h, 'last_7d': count_7d, 'status': status})

        return render_template('admin/reports.html', sales=sales, open_returns=open_returns, complaints=complaints)

    @app.route('/admin/reports/export')
    def admin_reports_export():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        now = datetime.utcnow()
        start_day = now - timedelta(days=1)
        start_week = now - timedelta(days=7)
        start_month = now - timedelta(days=30)

        def sum_total(rows):
            total = 0.0
            for row in rows:
                try:
                    total += float(row.total or 0)
                except Exception:
                    total += 0.0
            return total

        daily_orders = Order.query.filter(Order.created_at >= start_day).all()
        weekly_orders = Order.query.filter(Order.created_at >= start_week).all()
        monthly_orders = Order.query.filter(Order.created_at >= start_month).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['metric', 'value'])
        writer.writerow(['daily_sales', f"{sum_total(daily_orders):.2f}"])
        writer.writerow(['weekly_sales', f"{sum_total(weekly_orders):.2f}"])
        writer.writerow(['monthly_sales', f"{sum_total(monthly_orders):.2f}"])
        writer.writerow(['open_returns', ReturnRequest.query.filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested'])).count()])
        writer.writerow([])
        writer.writerow(['order_ref', 'status', 'total', 'created_at'])
        for order in monthly_orders:
            writer.writerow([
                order.order_ref or '',
                order.status or '',
                f"{float(order.total or 0):.2f}",
                order.created_at.isoformat() if order.created_at else '',
            ])

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=admin_reports_export.csv'},
        )

    @app.route('/admin/reports/export/excel')
    def admin_reports_export_excel():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        from openpyxl import Workbook
        from flask import Response

        now = datetime.utcnow()
        monthly_orders = Order.query.filter(Order.created_at >= now - timedelta(days=30)).all()
        total_sales = sum(float(row.total or 0) for row in monthly_orders)
        open_returns = ReturnRequest.query.filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested'])).count()

        wb = Workbook()
        ws = wb.active
        ws.title = 'Admin Reports'
        ws.append(['metric', 'value'])
        ws.append(['monthly_sales', round(total_sales, 2)])
        ws.append(['open_returns', open_returns])
        ws.append([])
        ws.append(['order_ref', 'status', 'total', 'created_at'])
        for row in monthly_orders:
            ws.append([
                row.order_ref or '',
                row.status or '',
                float(row.total or 0),
                row.created_at.isoformat() if row.created_at else '',
            ])

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return Response(
            stream.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=admin_reports.xlsx'},
        )

    @app.route('/admin/reports/export/pdf')
    def admin_reports_export_pdf():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
            from .models.return_request import ReturnRequest
        except Exception:
            from models.order import Order
            from models.return_request import ReturnRequest

        from flask import Response
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        now = datetime.utcnow()
        monthly_orders = Order.query.filter(Order.created_at >= now - timedelta(days=30)).all()
        total_sales = sum(float(row.total or 0) for row in monthly_orders)
        open_returns = ReturnRequest.query.filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested'])).count()

        stream = io.BytesIO()
        pdf = canvas.Canvas(stream, pagesize=letter)
        y = 760
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawString(50, y, 'Admin Report Summary (Last 30 Days)')
        y -= 26
        pdf.setFont('Helvetica', 11)
        pdf.drawString(50, y, f'Total Sales: PHP {total_sales:.2f}')
        y -= 18
        pdf.drawString(50, y, f'Open Returns: {open_returns}')
        y -= 24
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(50, y, 'Recent Orders')
        y -= 16
        pdf.setFont('Helvetica', 9)
        for row in monthly_orders[:25]:
            pdf.drawString(50, y, f"{row.order_ref or ''} | {row.status or ''} | PHP {float(row.total or 0):.2f}")
            y -= 13
            if y < 50:
                pdf.showPage()
                y = 760
        pdf.save()
        stream.seek(0)

        return Response(
            stream.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=admin_reports.pdf'},
        )

    # demo route removed per user request

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
