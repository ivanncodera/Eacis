from flask import Flask, render_template
from flask import redirect, url_for, request, jsonify, abort
from flask import flash, session
import time
import csv
import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
ALLOWED_AVATAR_EXT = ('png', 'jpg', 'jpeg', 'webp')
try:
    from PIL import Image
except Exception:
    Image = None
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
from eacis.extensions import db, csrf, login_manager, migrate
from eacis.validation import (
    join_name,
    EMAIL_PATTERN,
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
    sanitize_search_query,
    validate_search_query,
    normalize_phone,
)

 
# Global Utility Helpers & Model Imports
from eacis.models.user import User

def static_page_payload(page_id, title):
    return {
        'page_id': page_id,
        'page_title': title,
        'content_title': title.upper(),
        'last_updated': datetime.utcnow().strftime('%B %Y')
    }

def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)

    # Avatar upload configuration
    app.config.setdefault('MAX_AVATAR_UPLOAD_BYTES', 2 * 1024 * 1024)  # 2 MB
    app.config.setdefault('AVATAR_SIZES', [32, 128, 512])

    # Avatar helpers (scoped to this app)
    def _avatar_base(role):
        return os.path.join(app.instance_path, 'uploads', 'avatars', role)

    def _remove_avatar_files(role, uid):
        try:
            base = _avatar_base(role)
            if not os.path.isdir(base):
                return
            for fn in os.listdir(base):
                if fn.startswith(f"{uid}.") or fn.startswith(f"{uid}_"):
                    try:
                        os.remove(os.path.join(base, fn))
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_avatar(upload, role, uid):
        if not upload or not getattr(upload, 'filename', None):
            return False, 'No file uploaded.'
        filename = secure_filename(upload.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_AVATAR_EXT:
            return False, 'Invalid image format. Use PNG, JPG or WEBP.'
        # read bytes safely
        try:
            data = upload.read()
        except Exception:
            try:
                upload.stream.seek(0)
                data = upload.stream.read()
            except Exception:
                return False, 'Could not read uploaded file.'
        size = len(data or b'')
        if size > int(app.config.get('MAX_AVATAR_UPLOAD_BYTES', 2 * 1024 * 1024)):
            mb = int(app.config.get('MAX_AVATAR_UPLOAD_BYTES', 2 * 1024 * 1024) / 1024)
            return False, f'File too large. Maximum {mb} KB.'

        dest_dir = _avatar_base(role)
        os.makedirs(dest_dir, exist_ok=True)

        # If Pillow is unavailable, save the raw upload (best-effort)
        if Image is None:
            _remove_avatar_files(role, uid)
            dest_path = os.path.join(dest_dir, f"{uid}.{ext}")
            try:
                with open(dest_path, 'wb') as fh:
                    fh.write(data)
                return True, None
            except Exception:
                return False, 'Could not save uploaded image.'

        # Validate and process image via Pillow
        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
        except Exception:
            return False, 'Invalid image file.'
        try:
            img = Image.open(io.BytesIO(data)).convert('RGB')
        except Exception:
            return False, 'Invalid image file.'

        max_size = max(app.config.get('AVATAR_SIZES', [32, 128, 512]))
        if max(img.size) > max_size:
            ratio = max_size / float(max(img.size))
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # remove existing avatar files for this user
        _remove_avatar_files(role, uid)

        # Save canonical JPEG base and thumbnails
        try:
            base_path = os.path.join(dest_dir, f"{uid}.jpg")
            img.save(base_path, format='JPEG', quality=85)
            for s in app.config.get('AVATAR_SIZES', [32, 128, 512]):
                thumb = img.copy()
                thumb.thumbnail((s, s), Image.LANCZOS)
                thumb.save(os.path.join(dest_dir, f"{uid}_{s}.jpg"), format='JPEG', quality=85)
            return True, None
        except Exception:
            return False, 'Could not process and save image.'


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

    # Helper: check whether the product_images table exists (migration may not have been applied)
    from sqlalchemy import inspect as sqlalchemy_inspect
    def product_images_table_exists():
        try:
            return sqlalchemy_inspect(db.engine).has_table('product_images')
        except Exception:
            return False

    # Simple in-memory login guardrails for abuse control.
    # Structure: {(scope, identity): {'count': int, 'locked_until': float, 'window_start': float}}
    app._login_attempts = {}

    # Configure Flask-Login
    login_manager.login_view = 'auth_login'

    # Create simple dev users if DB is empty (development convenience)
    def ensure_dev_users():
        try:
            with app.app_context():
                db.create_all()
                try:
                    from eacis.models.voucher import Voucher
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
        from eacis.models.invoice import Invoice
        from eacis.models.order import OrderItem
        from eacis.models.product import Product

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

        # Use savepoints for per-invoice insertion to avoid whole-transaction failures
        from sqlalchemy.exc import IntegrityError
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
            # Attempt insertion within a savepoint; if it fails due to concurrency (unique constraint), skip.
            try:
                with db.session.begin_nested():
                    db.session.add(invoice)
                    db.session.flush()
                created.append(invoice)
            except IntegrityError:
                # Likely a concurrent insert created the same invoice; skip and continue
                continue
            except Exception:
                # Log and continue without aborting the caller transaction
                try:
                    app.logger.exception('Failed to create per-seller invoice')
                except Exception:
                    pass
                continue
        return created

    def calculate_refund_amount(order, seller_id=None):
        from eacis.models.order import OrderItem
        from eacis.models.product import Product

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
        try:
            from eacis.services import voucher_service as VchSvc
        except Exception:
            VchSvc = None
        
        if VchSvc:
            return VchSvc.validate_and_apply(voucher_code, cart_items, subtotal, customer_id)
            
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

    def can_view_product_id(user, product):
        """Return True when `user` is allowed to see internal product IDs.

        Rules:
        - Admins may see IDs.
        - Sellers may see IDs for products they own.
        - Customers may see IDs only if they have purchased/received the product (best-effort via helper).
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        role = getattr(user, 'role', None)
        if role == 'admin':
            return True
        try:
            if role == 'seller':
                # seller may see IDs for their own products
                return int(getattr(product, 'seller_id', 0) or 0) == int(getattr(user, 'id', 0) or 0)
        except Exception:
            pass

        if role == 'customer':
            try:
                # prefer dedicated helper which encapsulates delivered-order checks
                from eacis.services.review_service import has_user_received_product
                return bool(has_user_received_product(getattr(user, 'id', None), getattr(product, 'id', None)))
            except Exception:
                return False
        return False

    # expose helper on app for use in templates or other modules
    app.can_view_product_id = can_view_product_id

    # Make a template-level helper that checks visibility for the current user
    @app.context_processor
    def _inject_product_helpers():
        from flask_login import current_user
        from flask import url_for
        
        def _can_view(product):
            try:
                return bool(can_view_product_id(current_user, product))
            except Exception:
                return False

        def profile_image_url(user, size=None):
            try:
                if not user or not getattr(user, 'id', None):
                    return None
                role = getattr(user, 'role', 'customer') or 'customer'
                uid = int(getattr(user, 'id'))
                base = os.path.join(app.instance_path, 'uploads', 'avatars', role)
                # prefer size-specific thumbnails
                if size:
                    try:
                        s = int(size)
                        for ext in ALLOWED_AVATAR_EXT + ('jpg',):
                            fn = f"{uid}_{s}.{ext}"
                            if os.path.exists(os.path.join(base, fn)):
                                return url_for('serve_avatar', role=role, user_id=uid, size=s)
                    except Exception:
                        pass
                for ext in ALLOWED_AVATAR_EXT + ('jpg',):
                    fn = f"{uid}.{ext}"
                    if os.path.exists(os.path.join(base, fn)):
                        return url_for('serve_avatar', role=role, user_id=uid)
            except Exception:
                pass
            return None

        return {'can_view_product_id': _can_view, 'profile_image_url': profile_image_url}

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

    @app.route('/uploads/avatars/<role>/<int:user_id>')
    def serve_avatar(role, user_id):
        from flask import send_from_directory
        try:
            base = os.path.join(app.instance_path, 'uploads', 'avatars', role)
            if not os.path.isdir(base):
                abort(404)
            # optional size query param to request a thumbnail
            size = request.args.get('size') or None
            if size:
                try:
                    s = int(size)
                    # prefer generated jpg thumbnails
                    for ext in ALLOWED_AVATAR_EXT + ('jpg',):
                        fn = f"{user_id}_{s}.{ext}"
                        if os.path.exists(os.path.join(base, fn)):
                            return send_from_directory(base, fn)
                except Exception:
                    pass

            # fallback to base file
            for ext in ALLOWED_AVATAR_EXT + ('jpg',):
                fn = f"{user_id}.{ext}"
                if os.path.exists(os.path.join(base, fn)):
                    return send_from_directory(base, fn)
        except Exception:
            pass
        abort(404)

    @app.route('/api/postal/suggest')
    def postal_suggest():
        city = (request.args.get('city') or '').strip().lower()
        return jsonify({'city': city, 'postal_code': postal_lookup.get(city)})

    @app.route('/api/cart/summary')
    def api_cart_summary():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return jsonify({'items': [], 'count': 0, 'subtotal': 0.0})

        from eacis.models.cart import Cart
        from eacis.models.product import Product
        from eacis.models.voucher import Voucher
        from eacis.models.order import Order

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
                'product_id': int(product.id),
                'product_ref': product.product_ref,
                'name': product.name,
                'qty': qty,
                'unit_price': unit_price,
                'line_total': line_total,
                'image_url': product.image_url or '/static/assets/Featured.png',
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
        from eacis.models.product import Product
        from eacis.models.user import User

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
                'image_url': product.image_url or '/static/assets/Featured.png',
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
                'image_url': p.image_url or '/static/assets/Featured.png',
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
                'intro': 'These terms define account responsibilities, transaction conduct, returns and evidence workflows, and enforcement rules across customer, seller, and admin portals.',
                'principles': [
                    {'title': 'Account and Identity Integrity', 'description': 'Users must keep account details accurate and protect credential access.'},
                    {'title': 'Workflow Compliance', 'description': 'Orders, installments, inquiries, and returns must follow approved role-based platform flows.'},
                    {'title': 'Risk and Policy Enforcement', 'description': 'Abuse controls, return restrictions, and administrative actions may apply to policy violations.'},
                ],
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d'),
                'doc_ref': 'ACIS-TERMS-2026',
            },
            'privacy': {
                'intro': 'E-ACIS processes account, transaction, support, and security data to operate platform services while protecting user privacy.',
                'principles': [
                    {'title': 'Purpose-Limited Processing', 'description': 'Data is processed only for account access, commerce workflows, support, and compliance.'},
                    {'title': 'Controlled Access and Auditability', 'description': 'Role controls and operational logs help protect data and detect misuse.'},
                    {'title': 'Retention and Rights', 'description': 'Records are retained only as needed for service integrity and legal obligations, with data subject rights respected.'},
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
                
                # success - step-up via OTP
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

                # Enforce mandatory email verification: if account is unverified,
                # show a 'verify required' page and do not allow sign-in until verified.
                if not user.email_verified_at:
                    return render_template('auth/verify_required.html', email=user.email or '')

                purpose = 'login'
                otp_message = 'Check your email for the sign-in code.'

                # Trusted device bypass: if user has a valid trusted-device cookie, skip OTP.
                if purpose == 'login':
                    from eacis.services.trusted_device_service import find_by_token, touch
                    td_token = request.cookies.get(app.config.get('TRUSTED_DEVICE_COOKIE_NAME', 'trusted_device')) or request.cookies.get('trusted_device')
                    if td_token:
                        td = find_by_token(td_token)
                        if td and getattr(td, 'user_id', None) == user.id:
                            try:
                                touch(td)
                            except Exception:
                                app.logger.exception('Failed to touch trusted device')
                            from flask_login import login_user
                            login_user(user, remember=remember)
                            return redirect(dest)

                challenge, otp_error = start_otp_flow(
                    user=user,
                    purpose=purpose,
                    next_url=dest,
                    remember=remember if purpose == 'login' else False,
                    mode='login' if purpose == 'login' else 'register',
                    meta={'ip': client_ip, 'role': user.role},
                )
                if not challenge:
                    error = otp_error or 'Could not send OTP. Please try again.'
                    return render_template('auth/login.html', error=error)

                _reset_guardrails(email, client_ip)
                session['otp_message'] = otp_message
                return redirect(url_for('auth_otp_verify'))
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

    def save_return_evidence(upload_file, customer_id):
        if not upload_file or not upload_file.filename:
            return None, 'Missing evidence image file.'

        allowed = {'.png', '.jpg', '.jpeg', '.webp'}
        sanitized = secure_filename(upload_file.filename)
        ext = os.path.splitext(sanitized)[1].lower()
        if ext not in allowed:
            return None, 'Evidence images must be PNG, JPG, JPEG, or WEBP.'

        upload_file.stream.seek(0, os.SEEK_END)
        file_size = upload_file.stream.tell()
        upload_file.stream.seek(0)
        if file_size > (5 * 1024 * 1024):
            return None, 'Each evidence image must be 5MB or less.'

        upload_dir = os.path.join(app.instance_path, 'uploads', 'returns')
        os.makedirs(upload_dir, exist_ok=True)
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        filename = f"cust{customer_id}_{ts}_{sanitized}"
        abs_path = os.path.join(upload_dir, filename)
        try:
            upload_file.save(abs_path)
        except Exception:
            try:
                app.logger.exception('Failed to save return evidence file')
            except Exception:
                pass
            return None, 'Failed to save evidence image. Please try again.'
        return f"returns/{filename}", None

    def clear_otp_session():
        for key in (
            'otp_challenge_id',
            'otp_purpose',
            'otp_user_id',
            'otp_email',
            'otp_next',
            'otp_remember',
            'otp_mode',
            'otp_message',
            'password_reset_verified',
            'password_reset_user_id',
            'password_reset_email',
        ):
            session.pop(key, None)

    def clear_installment_otp_session():
        for key in ('installment_otp_verified', 'installment_otp_verified_at'):
            session.pop(key, None)

    def clear_email_change_session():
        for key in (
            'pending_email_change_email',
            'pending_email_change_user_id',
            'pending_email_change_old_email',
        ):
            session.pop(key, None)

    def clear_seller_security_session():
        for key in ('seller_security_otp_verified', 'seller_security_otp_verified_at'):
            session.pop(key, None)

    def clear_customer_security_session():
        for key in ('customer_security_otp_verified', 'customer_security_otp_verified_at'):
            session.pop(key, None)

    def clear_admin_action_session():
        for key in ('admin_action_otp_verified', 'admin_action_otp_verified_at', 'pending_admin_action'):
            session.pop(key, None)

    def clear_cancel_order_session():
        for key in ('order_cancel_otp_verified', 'order_cancel_otp_verified_at', 'pending_order_cancel_ref'):
            session.pop(key, None)

    def clear_seller_refund_session():
        for key in ('seller_refund_otp_verified', 'seller_refund_otp_verified_at', 'pending_seller_refund_rrt_ref'):
            session.pop(key, None)

    def is_admin_action_otp_fresh():
        if not session.get('admin_action_otp_verified'):
            return False
        stamp = session.get('admin_action_otp_verified_at')
        if not stamp:
            return False
        try:
            verified_at = datetime.fromisoformat(str(stamp))
            if verified_at.tzinfo is not None:
                verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return False
        return (datetime.utcnow() - verified_at).total_seconds() <= 900

    def is_order_cancel_otp_fresh():
        if not session.get('order_cancel_otp_verified'):
            return False
        stamp = session.get('order_cancel_otp_verified_at')
        if not stamp:
            return False
        try:
            verified_at = datetime.fromisoformat(str(stamp))
            if verified_at.tzinfo is not None:
                verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return False
        return (datetime.utcnow() - verified_at).total_seconds() <= 900

    def is_seller_refund_otp_fresh():
        if not session.get('seller_refund_otp_verified'):
            return False
        stamp = session.get('seller_refund_otp_verified_at')
        if not stamp:
            return False
        try:
            verified_at = datetime.fromisoformat(str(stamp))
            if verified_at.tzinfo is not None:
                verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return False
        return (datetime.utcnow() - verified_at).total_seconds() <= 900

    def is_seller_security_otp_fresh():
        if not session.get('seller_security_otp_verified'):
            return False
        stamp = session.get('seller_security_otp_verified_at')
        if not stamp:
            return False
        try:
            verified_at = datetime.fromisoformat(str(stamp))
            if verified_at.tzinfo is not None:
                verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return False
        return (datetime.utcnow() - verified_at).total_seconds() <= 900

    def is_customer_security_otp_fresh():
        if not session.get('customer_security_otp_verified'):
            return False
        stamp = session.get('customer_security_otp_verified_at')
        if not stamp:
            return False
        try:
            verified_at = datetime.fromisoformat(str(stamp))
            if verified_at.tzinfo is not None:
                verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return False
        return (datetime.utcnow() - verified_at).total_seconds() <= 900

    def is_installment_otp_fresh():
        if not session.get('installment_otp_verified'):
            return False
        stamp = session.get('installment_otp_verified_at')
        if not stamp:
            return False
        try:
            verified_at = datetime.fromisoformat(str(stamp))
            if verified_at.tzinfo is not None:
                verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return False
        return (datetime.utcnow() - verified_at).total_seconds() <= 900

    def start_otp_flow(*, user, purpose, next_url='', remember=False, mode='auth', meta=None, email_override=None):
        from eacis.services.otp_service import create_and_send_otp

        target_email = (email_override or user.email or '').strip().lower()

        challenge, message = create_and_send_otp(
            target_email,
            purpose,
            user_id=user.id,
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
            user_agent=(request.headers.get('User-Agent') or '')[:255],
            meta=meta or {},
        )
        if not challenge:
            return None, message

        session['otp_challenge_id'] = challenge.id
        session['otp_purpose'] = purpose
        session['otp_user_id'] = user.id
        session['otp_email'] = target_email
        session['otp_next'] = next_url or ''
        session['otp_remember'] = bool(remember)
        session['otp_mode'] = mode
        return challenge, None

    def finalize_customer_order_cancel(customer, order_ref):
        from eacis.models.order import Order, OrderItem
        from eacis.models.voucher import Voucher
        from eacis.models.loyalty import LoyaltyTransaction

        try:
            from eacis.services import inventory_service as InvSvc
        except Exception:
            InvSvc = None

        order = Order.query.filter_by(order_ref=order_ref, customer_id=customer.id).first()
        if not order:
            return False, 'Order not found.'

        cancellable = False
        if order.status == 'pending':
            cancellable = True
        elif order.status == 'paid' and order.paid_at:
            elapsed = (datetime.utcnow() - order.paid_at).total_seconds()
            cancellable = elapsed <= 3600

        if not cancellable:
            return False, 'This order cannot be cancelled at its current stage.'

        try:
            for item in OrderItem.query.filter_by(order_id=order.id).all():
                if item.product and InvSvc:
                    InvSvc.restore_on_cancel(item.product, item.quantity, order_ref, customer.id)
                elif item.product:
                    item.product.stock = int(item.product.stock or 0) + int(item.quantity or 0)

            if order.voucher_id:
                voucher = Voucher.query.get(order.voucher_id)
                if voucher:
                    voucher.uses_count = max(0, int(voucher.uses_count or 1) - 1)

            if order.loyalty_redeemed and int(order.loyalty_redeemed) > 0:
                customer.loyalty_points = int(customer.loyalty_points or 0) + int(order.loyalty_redeemed)
                db.session.add(LoyaltyTransaction(
                    user_id=customer.id,
                    type='earn',
                    points=int(order.loyalty_redeemed),
                    reference=order_ref,
                    note='Restored from order cancellation',
                ))

            order.status = 'cancelled'
            db.session.commit()
            return True, f'Order {order_ref} has been cancelled. Stock and benefits restored.'
        except Exception:
            db.session.rollback()
            return False, 'Could not cancel order. Please try again.'

    def finalize_seller_refund(seller, rrt_ref):
        from eacis.models.return_request import ReturnRequest
        from eacis.models.order import Order, OrderItem

        try:
            from eacis.services import return_service as RetSvc
        except Exception:
            RetSvc = None

        if not RetSvc:
            return False, 'Return service unavailable. Contact admin.'

        return_request = ReturnRequest.query.filter_by(rrt_ref=rrt_ref).first()
        if not return_request:
            return False, 'Return request not found.'

        seller_has_item = False
        for item in OrderItem.query.filter_by(order_id=return_request.order_id).all():
            if item.product and item.product.seller_id == seller.id:
                seller_has_item = True
                break
        if not seller_has_item:
            return False, 'You do not have access to this return request.'

        order = Order.query.get(return_request.order_id)
        seller_refund_amount = calculate_refund_amount(order, seller_id=seller.id)
        if seller_refund_amount <= 0:
            seller_refund_amount = float(return_request.refund_amount or 0)

        success, msg = RetSvc.process_refund(
            return_request.id,
            seller_id=seller.id,
            amount=seller_refund_amount,
        )
        return success, msg

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
                    email_verified_at=None,
                )
                new_user.set_password(normalized['password'])
                db.session.add(new_user)
                db.session.commit()
                challenge, otp_error = start_otp_flow(
                    user=new_user,
                    purpose='register_verify',
                    next_url=url_for('shop'),
                    mode='register',
                    meta={'role': 'customer'},
                )
                if not challenge:
                    db.session.delete(new_user)
                    db.session.commit()
                    errors['general'] = otp_error or 'Could not send verification code.'
                    return render_template('auth/register_customer.html', errors=errors, form=normalized)
                flash('We sent a verification code to your email. Enter it to activate your account.', 'success')
                return redirect(url_for('auth_verify_required'))
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
                    email_verified_at=None,
                )
                new_user.set_password(normalized['password'])
                db.session.add(new_user)
                db.session.commit()
                challenge, otp_error = start_otp_flow(
                    user=new_user,
                    purpose='register_verify',
                    next_url=url_for('seller_dashboard'),
                    mode='register',
                    meta={'role': 'seller'},
                )
                if not challenge:
                    db.session.delete(new_user)
                    db.session.commit()
                    errors['general'] = otp_error or 'Could not send verification code.'
                    return render_template('auth/register_seller.html', errors=errors, form=normalized)
                flash('We sent a verification code to your email. Enter it to activate your seller account.', 'success')
                return redirect(url_for('auth_verify_required'))
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

    @app.route('/auth/otp/verify', methods=['GET', 'POST'])
    def auth_otp_verify():
        try:
            from .models.user import User
            from .models.otp_challenge import OtpChallenge
        except Exception:
            from models.user import User
            from models.otp_challenge import OtpChallenge

        challenge_id = session.get('otp_challenge_id')
        purpose = session.get('otp_purpose') or 'login'
        otp_email = session.get('otp_email') or ''
        challenge_row = OtpChallenge.query.get(challenge_id) if challenge_id else None
        debug_code = ''
        if challenge_row and challenge_row.meta and isinstance(challenge_row.meta, dict):
            debug_code = challenge_row.meta.get('debug_code') or ''
        if not challenge_id:
            flash('No OTP challenge is active. Please start again.', 'error')
            return redirect(url_for('auth_login'))

        if request.method == 'POST':
            code = (request.form.get('otp_code') or request.form.get('code') or '').strip()
            if len(code) < 4:
                return render_template('auth/otp_verify.html', purpose=purpose, email=otp_email, error='Enter the one-time code from your email.', message=session.get('otp_message', ''), debug_code=debug_code)

            from eacis.services.otp_service import verify_otp

            ok, message = verify_otp(challenge_id, code)
            if not ok:
                return render_template('auth/otp_verify.html', purpose=purpose, email=otp_email, error=message, message=session.get('otp_message', ''), debug_code=debug_code)

            user = User.query.get(session.get('otp_user_id')) if session.get('otp_user_id') else None
            remember = bool(session.get('otp_remember'))
            remember_device = bool(request.form.get('remember_device'))
            next_url = session.get('otp_next') or ''

            if purpose == 'register_verify':
                if user and not user.email_verified_at:
                    user.email_verified_at = datetime.utcnow()
                    db.session.commit()
                from flask_login import login_user
                if user:
                    login_user(user, remember=False)
                # If user opted to remember this device, create a trusted-device token and set cookie.
                target = next_url or (url_for('seller_dashboard') if user and user.role == 'seller' else url_for('shop'))
                if user and remember_device:
                    try:
                        from eacis.services.trusted_device_service import create_trusted_device
                        device_name = (request.headers.get('User-Agent') or '')[:255]
                        days = app.config.get('TRUSTED_DEVICE_DAYS', 30)
                        token, td = create_trusted_device(user.id, device_name=device_name, days_valid=days)
                        resp = redirect(target)
                        cookie_name = app.config.get('TRUSTED_DEVICE_COOKIE_NAME', 'trusted_device')
                        resp.set_cookie(cookie_name, token, max_age=days * 24 * 3600, httponly=True, secure=app.config.get('SESSION_COOKIE_SECURE', True), samesite='Lax', path='/')
                        clear_otp_session()
                        flash('Email verified. Your account is now active.', 'success')
                        return resp
                    except Exception:
                        app.logger.exception('Failed to create trusted device token')
                clear_otp_session()
                flash('Email verified. Your account is now active.', 'success')
                return redirect(target)

            if purpose == 'password_reset':
                session['password_reset_verified'] = True
                session['password_reset_user_id'] = session.get('otp_user_id')
                session['password_reset_email'] = otp_email
                # Keep reset context; clear the one-time challenge only.
                session.pop('otp_challenge_id', None)
                session.pop('otp_purpose', None)
                session.pop('otp_mode', None)
                session.pop('otp_remember', None)
                flash('Code verified. You can now set a new password.', 'success')
                return redirect(url_for('auth_reset_password'))

            if purpose == 'installment_confirm':
                session['installment_otp_verified'] = True
                session['installment_otp_verified_at'] = datetime.utcnow().isoformat()
                clear_otp_session()
                flash('Installment verification complete. You can now confirm your order.', 'success')
                return redirect(next_url or url_for('customer_checkout_installment_confirm'))

            if purpose == 'email_change':
                pending_email = (session.get('pending_email_change_email') or otp_email or '').strip().lower()
                if not pending_email:
                    flash('Email change session expired. Please try again.', 'error')
                    clear_otp_session()
                    clear_email_change_session()
                    return redirect(url_for('customer_profile_edit'))
                if user:
                    user.email = pending_email
                    user.email_verified_at = datetime.utcnow()
                    db.session.commit()
                clear_otp_session()
                clear_email_change_session()
                flash('Your email address has been updated and verified.', 'success')
                return redirect(next_url or url_for('customer_profile_edit'))

            if purpose == 'seller_security':
                session['seller_security_otp_verified'] = True
                session['seller_security_otp_verified_at'] = datetime.utcnow().isoformat()
                clear_otp_session()
                flash('Security verification complete. You can now update your seller password.', 'success')
                return redirect(next_url or url_for('seller_security'))

            if purpose == 'customer_security':
                session['customer_security_otp_verified'] = True
                session['customer_security_otp_verified_at'] = datetime.utcnow().isoformat()
                clear_otp_session()
                flash('Security verification complete. You can now update your password.', 'success')
                return redirect(next_url or url_for('customer_security'))
            if purpose == 'admin_action':
                session['admin_action_otp_verified'] = True
                session['admin_action_otp_verified_at'] = datetime.utcnow().isoformat()
                clear_otp_session()
                flash('Admin verification complete. You can continue with the privileged action.', 'success')
                return redirect(next_url or url_for('admin_dashboard'))

            if purpose == 'order_cancel':
                session['order_cancel_otp_verified'] = True
                session['order_cancel_otp_verified_at'] = datetime.utcnow().isoformat()
                order_ref = session.get('pending_order_cancel_ref') or ''
                from flask_login import current_user
                if order_ref and current_user and getattr(current_user, 'is_authenticated', False):
                    success, result_message = finalize_customer_order_cancel(current_user, order_ref)
                    clear_otp_session()
                    clear_cancel_order_session()
                    if success:
                        flash(result_message, 'success')
                    else:
                        flash(result_message, 'error')
                    return redirect(url_for('customer_orders'))
                clear_otp_session()
                clear_cancel_order_session()
                flash('Order cancellation session expired. Please try again.', 'error')
                return redirect(url_for('customer_orders'))

            if purpose == 'seller_refund':
                session['seller_refund_otp_verified'] = True
                session['seller_refund_otp_verified_at'] = datetime.utcnow().isoformat()
                rrt_ref = session.get('pending_seller_refund_rrt_ref') or ''
                from flask_login import current_user
                if rrt_ref and current_user and getattr(current_user, 'is_authenticated', False):
                    success, result_message = finalize_seller_refund(current_user, rrt_ref)
                    clear_otp_session()
                    clear_seller_refund_session()
                    if success:
                        flash(result_message, 'success')
                    else:
                        flash(result_message, 'error')
                    return redirect(url_for('seller_returns'))
                clear_otp_session()
                clear_seller_refund_session()
                flash('Refund verification session expired. Please try again.', 'error')
                return redirect(url_for('seller_returns'))

            from flask_login import login_user
            if user:
                login_user(user, remember=remember)
            target = next_url or (url_for('seller_dashboard') if user and user.role == 'seller' else url_for('shop'))
            # If user asked to remember this device (from the OTP form) and this is a login flow, create trusted-device cookie.
            if user and remember_device and purpose == 'login':
                try:
                    from eacis.services.trusted_device_service import create_trusted_device
                    device_name = (request.headers.get('User-Agent') or '')[:255]
                    days = app.config.get('TRUSTED_DEVICE_DAYS', 30)
                    token, td = create_trusted_device(user.id, device_name=device_name, days_valid=days)
                    resp = redirect(target)
                    cookie_name = app.config.get('TRUSTED_DEVICE_COOKIE_NAME', 'trusted_device')
                    resp.set_cookie(cookie_name, token, max_age=days * 24 * 3600, httponly=True, secure=app.config.get('SESSION_COOKIE_SECURE', True), samesite='Lax', path='/')
                    clear_otp_session()
                    flash('OTP verified. You are now signed in.', 'success')
                    return resp
                except Exception:
                    app.logger.exception('Failed to create trusted device token')
            clear_otp_session()
            flash('OTP verified. You are now signed in.', 'success')
            return redirect(target)

        return render_template('auth/otp_verify.html', purpose=purpose, email=otp_email, error='', message=session.get('otp_message', ''), debug_code=debug_code)

    @app.route('/auth/verify-required')
    def auth_verify_required():
        # Shows instructions and resend option for unverified accounts
        email = (request.args.get('email') or session.get('otp_email') or '')
        return render_template('auth/verify_required.html', email=email)

    @app.route('/auth/register/verify/<token>')
    def auth_register_verify(token):
        try:
            from eacis.services.otp_service import verify_activation_token
        except Exception:
            verify_activation_token = None

        if not verify_activation_token:
            flash('Verification is currently unavailable.', 'error')
            return redirect(url_for('auth_login'))

        ok, message, chal = verify_activation_token(token)
        if not ok:
            flash(message or 'Invalid or expired verification link.', 'error')
            return redirect(url_for('auth_login'))

        if not chal or chal.purpose != 'register_verify':
            flash('Verification challenge not found or invalid.', 'error')
            return redirect(url_for('auth_login'))

        user = None
        try:
            if chal and chal.user_id:
                user = User.query.get(chal.user_id)
        except Exception:
            user = None

        if not user:
            flash('Account not found.', 'error')
            return redirect(url_for('auth_login'))

        try:
            user.email_verified_at = datetime.utcnow()
            db.session.commit()
            from eacis.models.audit import AuditLog
            try:
                db.session.add(AuditLog(
                    actor_id=user.id,
                    actor_name=getattr(user, 'full_name', None) or user.email,
                    role=user.role,
                    action='email_verified',
                    module='auth',
                    target_ref=user.email,
                    meta={'via': 'register_link'},
                    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
        except Exception:
            db.session.rollback()

        try:
            from flask_login import login_user
            login_user(user, remember=False)
        except Exception:
            pass
        clear_otp_session()
        flash('Email verified. Your account is now active.', 'success')
        return redirect(url_for('shop'))

    @app.route('/auth/otp/resend', methods=['POST'])
    def auth_otp_resend():
        challenge_id = session.get('otp_challenge_id')
        purpose = session.get('otp_purpose') or 'login'
        user_id = session.get('otp_user_id')
        if not challenge_id or not user_id:
            flash('No OTP challenge is active.', 'error')
            return redirect(url_for('auth_login'))

        try:
            from .models.user import User
        except Exception:
            from models.user import User

        user = User.query.get(user_id)
        if not user:
            flash('Unable to resend OTP for this account.', 'error')
            return redirect(url_for('auth_login'))

        from eacis.services.otp_service import create_and_send_otp

        challenge, message = create_and_send_otp(
            user.email,
            purpose,
            user_id=user.id,
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
            user_agent=(request.headers.get('User-Agent') or '')[:255],
            meta={'resend': True},
        )
        if not challenge:
            flash(message or 'Could not resend OTP right now.', 'error')
            return redirect(url_for('auth_otp_verify'))

        session['otp_challenge_id'] = challenge.id
        flash('We sent a new verification code.', 'success')
        return redirect(url_for('auth_otp_verify'))


    @app.route('/auth/otp/send', methods=['POST'])
    def auth_otp_send():
        try:
            from .models.user import User
        except Exception:
            from models.user import User

        # prefer logged-in user context when available
        try:
            from flask_login import current_user
        except Exception:
            current_user = None

        email = (request.form.get('email') or '').strip().lower()
        purpose = (request.form.get('purpose') or 'login').strip()

        user = None
        if current_user and getattr(current_user, 'is_authenticated', False):
            user = current_user
        else:
            if not email:
                flash('Missing email address.', 'error')
                return redirect(url_for('auth_login'))
            user = User.query.filter_by(email=email).first()
            if not user:
                # Don't leak existence; show generic success
                flash('If the email exists, a verification code has been sent.', 'success')
                return redirect(url_for('auth_login'))

        from eacis.services.otp_service import create_and_send_otp

        challenge, message = create_and_send_otp(
            user.email,
            purpose,
            user_id=user.id,
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
            user_agent=(request.headers.get('User-Agent') or '')[:255],
            meta={'via': 'otp_send_route'},
        )
        if not challenge:
            flash(message or 'Could not send OTP right now.', 'error')
            return redirect(url_for('auth_login'))

        session['otp_challenge_id'] = challenge.id
        session['otp_purpose'] = purpose
        session['otp_user_id'] = user.id
        session['otp_email'] = user.email
        flash('A verification code was sent to the provided email.', 'success')
        return redirect(url_for('auth_verify_required'))

    @app.route('/auth/forgot-password', methods=['GET', 'POST'])
    def auth_forgot_password():
        try:
            from .models.user import User
        except Exception:
            from models.user import User

        if request.method == 'POST':
            email = (request.form.get('email') or '').strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user:
                return render_template('auth/forgot_password.html', error='If the email exists, we sent a reset code.'), 200

            challenge, otp_error = start_otp_flow(
                user=user,
                purpose='password_reset',
                next_url=url_for('auth_reset_password'),
                mode='password_reset',
                meta={'flow': 'password_reset'},
            )
            if not challenge:
                return render_template('auth/forgot_password.html', error=otp_error or 'Could not send reset code.', email=email), 200

            flash('We sent a password reset code to your email.', 'success')
            return redirect(url_for('auth_otp_verify'))

        return render_template('auth/forgot_password.html', error='')

    @app.route('/auth/reset-password', methods=['GET', 'POST'])
    def auth_reset_password():
        try:
            from .models.user import User
        except Exception:
            from models.user import User

        if not session.get('password_reset_verified') or not session.get('password_reset_user_id'):
            flash('Verify the reset code first.', 'error')
            return redirect(url_for('auth_forgot_password'))

        if request.method == 'POST':
            password = request.form.get('password') or ''
            confirm = request.form.get('confirm_password') or ''
            if len(password) < 8:
                return render_template('auth/reset_password.html', error='Password must be at least 8 characters.'), 200
            if password != confirm:
                return render_template('auth/reset_password.html', error='Passwords do not match.'), 200

            user = User.query.get(session.get('password_reset_user_id'))
            if not user:
                flash('Account not found.', 'error')
                clear_otp_session()
                return redirect(url_for('auth_forgot_password'))

            user.set_password(password)
            db.session.commit()
            try:
                try:
                    from .models.audit import AuditLog
                except Exception:
                    from models.audit import AuditLog
                try:
                    db.session.add(AuditLog(
                        actor_id=user.id,
                        actor_name=getattr(user, 'full_name', None) or user.email,
                        role=user.role,
                        action='password_reset',
                        module='auth',
                        target_ref=user.email,
                        meta={'flow': 'password_reset'},
                        ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                    ))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            except Exception:
                try:
                    app.logger.exception('Failed to record password reset audit')
                except Exception:
                    pass
            clear_otp_session()
            flash('Password updated. Please sign in again.', 'success')
            return redirect(url_for('auth_login'))

        return render_template('auth/reset_password.html', error='')

    @app.route('/terms')
    def terms_of_service():
        return render_template('terms.html')

    @app.route('/privacy')
    def privacy_policy():
        return render_template('privacy.html')

    @app.route('/data-compliance')
    def data_compliance():
        return render_template('data_compliance.html')

    @app.route('/whats-new')
    def whats_new():
        # Render the release notes page showing local changes since last push
        return render_template('release_notes.html')

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
        # load ordered product images (position) for display
        try:
            from .models.product_image import ProductImage
        except Exception:
            from models.product_image import ProductImage

        images = []
        if product and product_images_table_exists():
            try:
                images = ProductImage.query.filter_by(product_id=product.id).order_by(ProductImage.position.asc()).all()
            except Exception:
                images = []
        # Review aggregates and star state
        from eacis.services.review_service import get_aggregate, get_reviews, has_user_received_product

        try:
            from .models.product_star import ProductStar
        except Exception:
            from models.product_star import ProductStar

        agg = get_aggregate(product.id) if product else {'count': 0, 'avg': 0.0}
        reviews_list = get_reviews(product.id, limit=5, offset=0) if product else []
        star_count = ProductStar.query.filter_by(product_id=product.id).count() if product else 0
        starred_by_user = False
        try:
            from flask_login import current_user
            if current_user and getattr(current_user, 'is_authenticated', False):
                starred_by_user = bool(ProductStar.query.filter_by(product_id=product.id, user_id=current_user.id).first())
        except Exception:
            starred_by_user = False

        # Determine whether current user can leave a review (must be a customer who received the product)
        can_review = False
        try:
            from flask_login import current_user
            if current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer':
                try:
                    can_review = bool(has_user_received_product(current_user.id, product.id))
                except Exception:
                    can_review = False
        except Exception:
            can_review = False

        return render_template('customer/product_detail.html', product=product, related_products=related_products, images=images, reviews=reviews_list, review_agg=agg, star_count=star_count, starred_by_user=starred_by_user, can_review=can_review)

    @app.route('/products/<ref>/star', methods=['POST'])
    def product_star(ref):
        try:
            from flask_login import current_user
        except Exception:
            current_user = None
        if not (current_user and getattr(current_user, 'is_authenticated', False)):
            return jsonify({'error': 'Authentication required.'}), 401

        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        product = Product.query.filter_by(product_ref=ref, is_active=True).first()
        if not product:
            return jsonify({'error': 'Product not found.'}), 404

        from eacis.services.review_service import toggle_star, has_user_received_product

        # Early purchase check to prevent non-purchasers from starring
        try:
            if not has_user_received_product(current_user.id, product.id):
                return jsonify({'error': 'Only customers who purchased and received this product may star it.'}), 403
        except Exception:
            # fall back to service-level enforcement below
            pass

        result, err = toggle_star(current_user.id, product.id, require_purchase=True)
        if err:
            return jsonify({'error': err}), 500
        return jsonify(result)

    @app.route('/products/<ref>/reviews', methods=['POST'])
    def product_create_review(ref):
        try:
            from flask_login import current_user
        except Exception:
            current_user = None

        if not (current_user and getattr(current_user, 'is_authenticated', False)):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.product import Product
        except Exception:
            from models.product import Product

        product = Product.query.filter_by(product_ref=ref, is_active=True).first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('shop'))

        rating = request.form.get('rating')
        title = request.form.get('title')
        body = request.form.get('body')

        from eacis.services.review_service import create_or_update_review, has_user_received_product

        is_anonymous = True if (request.form.get('is_anonymous') or '').lower() in ('1','true','on','yes') else False

        # Early check to avoid attempting to accept reviews from non-purchasers
        try:
            if not has_user_received_product(current_user.id, product.id):
                flash('Only customers who purchased and received this product may submit a review.', 'error')
                return redirect(url_for('product_detail', ref=ref))
        except Exception:
            # If the helper fails, fall back to service-level validation below
            pass

        rv, err = create_or_update_review(current_user.id, product.id, rating, title=title, body=body, is_anonymous=is_anonymous, require_purchase=True)
        if err:
            flash(err, 'error')
        else:
            flash('Review submitted.', 'success')
        return redirect(url_for('product_detail', ref=ref))

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
                product_ref = (request.form.get('product_ref') or '').strip()
                # fallback: resolve by ref when numeric id not provided
                if not product_id and product_ref:
                    try:
                        ptmp = Product.query.filter_by(product_ref=product_ref).first()
                        product_id = int(ptmp.id) if ptmp else None
                    except Exception:
                        product_id = None

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
                    try:
                        if int(item.get('product_id')) == int(product_id):
                            item['qty'] = qty
                            updated = True
                            break
                    except Exception:
                        continue
                if updated:
                    cart.items = items
                    db.session.commit()
                    flash('Cart updated.', 'success')
            elif action == 'remove':
                product_id = request.form.get('product_id', type=int)
                product_ref = (request.form.get('product_ref') or '').strip()
                if not product_id and product_ref:
                    try:
                        ptmp = Product.query.filter_by(product_ref=product_ref).first()
                        product_id = int(ptmp.id) if ptmp else None
                    except Exception:
                        product_id = None

                try:
                    if product_id is not None:
                        cart.items = [item for item in items if int(item.get('product_id')) != int(product_id)]
                        db.session.commit()
                        flash('Item removed from cart.', 'success')
                    else:
                        flash('Item not found.', 'error')
                except Exception:
                    flash('Could not remove item.', 'error')
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
            from .models.address import Address
        except Exception:
            from models.cart import Cart
            from models.order import Order, OrderItem
            from models.product import Product
            from models.voucher import Voucher
            from models.loyalty import LoyaltyTransaction
            from models.installment import InstallmentPlan, InstallmentSchedule
            from models.address import Address

        cart = Cart.query.filter_by(user_id=current_user.id).first()

        # Allow passing a selection of items to checkout via ?selected=ref1&selected=ref2
        selected_refs = []
        try:
            # Prefer querystring for GET flows, but also accept POSTed selections
            selected_refs = request.args.getlist('selected') or []
        except Exception:
            selected_refs = []
        if request.method == 'POST' and not selected_refs:
            try:
                selected_refs = request.form.getlist('selected') or []
            except Exception:
                selected_refs = []

        selected_ids = set()
        if selected_refs:
            try:
                sel_prods = Product.query.filter(Product.product_ref.in_(selected_refs)).all()
                selected_ids = set([int(p.id) for p in sel_prods if getattr(p, 'id', None) is not None])
            except Exception:
                selected_ids = set()

        cart_items = []
        subtotal = 0.0
        if cart and cart.items:
            for entry in cart.items:
                try:
                    pid = int(entry.get('product_id') or 0)
                except Exception:
                    pid = None
                # If a selection was provided, skip entries not in the selection
                if selected_ids and (not pid or pid not in selected_ids):
                    continue
                product = Product.query.get(entry.get('product_id'))
                if not product:
                    continue
                quantity = max(int(entry.get('qty') or 1), 1)
                line_total = money(float(product.price or 0) * quantity)
                subtotal += line_total
                cart_items.append({'product': product, 'qty': quantity, 'line_total': line_total})

        if not cart_items:
            flash('Your shopping bag is empty. Please add items before checking out.', 'error')
            return redirect(url_for('cart'))

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
        # prepare display phone without leading zero (UI uses +63 prefix)
        _norm = normalize_phone(current_user.phone) if getattr(current_user, 'phone', None) else ''
        display_phone = _norm[1:] if _norm and _norm.startswith('0') else (_norm or '')
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
            'phone': display_phone,
            'plan_months': 12,
        }

        # saved addresses for this user
        try:
            saved_addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
        except Exception:
            saved_addresses = []

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

        # handle saved address selection and optional save
        if request.method == 'POST':
            address_id = request.form.get('address_id', 'new')
            if address_id and address_id != 'new':
                try:
                    addr = Address.query.get(int(address_id))
                    if addr and addr.user_id == current_user.id:
                        checkout_form.update({
                            'recipient_name': addr.recipient_name or checkout_form.get('recipient_name'),
                            'address_line1': ', '.join([p for p in [addr.address_line1, addr.address_line2, addr.barangay, addr.city_municipality, addr.province, addr.region] if p]),
                            'postal_code': addr.postal_code or '',
                            'phone': addr.phone[1:] if addr.phone and addr.phone.startswith('0') else (addr.phone or '')
                        })
                except Exception:
                    pass

            if request.form.get('save_address') and address_id == 'new':
                try:
                    new_addr = Address(
                        user_id=current_user.id,
                        label=(request.form.get('save_label') or '').strip(),
                        recipient_name=checkout_form.get('recipient_name'),
                        phone=(normalize_phone(checkout_form.get('phone')) or None),
                        address_line1=(request.form.get('address_line1') or '').strip(),
                        address_line2=(request.form.get('address_line2') or '').strip(),
                        barangay=(request.form.get('barangay') or '').strip(),
                        city_municipality=(request.form.get('city_municipality') or '').strip(),
                        province=(request.form.get('province') or '').strip(),
                        region=(request.form.get('region') or '').strip(),
                        postal_code=(request.form.get('postal_code') or '').strip(),
                        is_default=bool(request.form.get('set_default'))
                    )
                    if new_addr.is_default:
                        Address.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
                    db.session.add(new_addr)
                    db.session.commit()
                    saved_addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
                except Exception:
                    db.session.rollback()

        requested_loyalty_before_clamp = int(loyalty_requested)

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
        if request.method == 'POST' and checkout_form and requested_loyalty_before_clamp > int(available_points):
            flash('Requested loyalty points exceed your available balance. We applied the maximum allowed points.', 'warning')
        elif request.method == 'POST' and checkout_form and requested_loyalty_before_clamp > int(max_loyalty_value):
            flash('Requested loyalty points exceed the payable amount after voucher discount. We applied the allowed maximum.', 'warning')
        discount_total = money(voucher_discount + float(loyalty_applied))
        order_total = money(max(subtotal - discount_total, 0.0))
        earned_points = int(order_total // 100)

        if request.method == 'POST':
            if not cart_items:
                flash('Your cart is empty.', 'error')
                return redirect(url_for('cart'))

            checkout_action = (request.form.get('action') or 'place_order').strip()

            # ── Server-side Terms enforcement for full_pay ────────────────
            if checkout_action == 'place_order' and request.form.get('payment') != 'installment':
                if request.form.get('agree_terms') != '1':
                    checkout_errors['general'] = 'You must agree to the Terms of Service and Privacy Policy to place an order.'
                    return render_template('customer/checkout.html',
                        cart_items=cart_items, subtotal=subtotal,
                        voucher_code=voucher_code, voucher_discount=voucher_discount,
                        loyalty_requested=int(loyalty_requested), loyalty_applied=int(loyalty_applied),
                        available_points=int(available_points), order_total=order_total,
                        earned_points=int(earned_points), selected_payment=selected_payment,
                        checkout_form=checkout_form, checkout_errors=checkout_errors, saved_addresses=saved_addresses)
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
                    saved_addresses=saved_addresses,
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
                    saved_addresses=saved_addresses,
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

                # ── Installment eligibility gate ──────────────────────────
                try:
                    from eacis.services import installment_service as InstSvc
                except Exception:
                    InstSvc = None
                if InstSvc:
                    # Keep overdue states fresh before checking eligibility.
                    try:
                        InstSvc.sync_overdue_schedules()
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    _elig, _disq = InstSvc.check_installment_eligibility(current_user.id)
                    if not _elig:
                        checkout_errors['payment'] = 'Installment not available: ' + '; '.join(_disq)
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
                            saved_addresses=saved_addresses,
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

            def _kyc_is_fresh():
                verified = bool(session.get('kyc_verified'))
                stamp = session.get('kyc_verified_at')
                if not (verified and stamp):
                    return False
                try:
                    verified_at = datetime.fromisoformat(str(stamp))
                    if verified_at.tzinfo is not None:
                        verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
                except Exception:
                    return False
                return (datetime.utcnow() - verified_at).total_seconds() <= 900  # 15 min window

            try:
                if payment_method == 'installment' and request.form.get('agree_terms') != '1':
                    checkout_errors['general'] = 'You must agree to the Terms of Service and Privacy Policy before placing an installment order.'
                    return render_template('customer/checkout.html',
                        cart_items=cart_items, subtotal=subtotal,
                        voucher_code=voucher_code, voucher_discount=voucher_discount,
                        loyalty_requested=int(loyalty_requested), loyalty_applied=int(loyalty_applied),
                        available_points=int(available_points), order_total=order_total,
                        earned_points=int(earned_points), selected_payment=selected_payment,
                        checkout_form=checkout_form, checkout_errors=checkout_errors)

                if payment_method == 'installment' and request.form.get('installment_confirmed') != 'true':
                    # ── Redirect to KYC gate first, then installment confirm ─
                    session['pending_checkout'] = {
                        'data': checkout_data,
                        'order_total': float(order_total),
                        'plan_months': plan_months,
                        'voucher_id': voucher.id if voucher else None,
                        'loyalty_applied': int(loyalty_applied)
                    }
                    # If KYC not yet done this session, go to KYC first
                    if not _kyc_is_fresh():
                        return redirect(url_for('customer_checkout_kyc'))
                    if not is_installment_otp_fresh():
                        challenge, otp_error = start_otp_flow(
                            user=current_user,
                            purpose='installment_confirm',
                            next_url=url_for('customer_checkout_installment_confirm'),
                            mode='checkout',
                            meta={'flow': 'installment_checkout', 'order_total': float(order_total), 'plan_months': int(plan_months)},
                        )
                        if not challenge:
                            checkout_errors['general'] = otp_error or 'Could not send installment verification code.'
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
                                saved_addresses=saved_addresses,
                            )
                        session['otp_message'] = 'Check your email to confirm this installment order.'
                        return redirect(url_for('auth_otp_verify'))
                    return redirect(url_for('customer_checkout_installment_confirm'))

                if payment_method == 'installment' and request.form.get('installment_confirmed') == 'true':
                    pending = session.get('pending_checkout') or {}
                    if not _kyc_is_fresh() or not pending:
                        checkout_errors['general'] = 'Identity verification expired or missing. Please verify again before confirming installment.'
                        return redirect(url_for('customer_checkout_kyc'))
                    if not is_installment_otp_fresh():
                        checkout_errors['general'] = 'Installment verification code expired or missing. Please verify again before confirming.'
                        return redirect(url_for('customer_checkout_installment_confirm'))

                    pending_total = float(pending.get('order_total') or 0)
                    pending_months = int(pending.get('plan_months') or 0)
                    if abs(float(order_total) - pending_total) > 0.01 or int(plan_months) != pending_months:
                        checkout_errors['general'] = 'Installment summary changed. Please review and confirm the updated plan again.'
                        flash(checkout_errors['general'], 'error')
                        return redirect(url_for('checkout'))

                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_count = Order.query.filter(Order.created_at >= today_start).count() + 1
                order_ref = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}{str(today_count).zfill(5)}"
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
                # ── Stock deduction with audit trail ─────────────────
                try:
                    from eacis.services import inventory_service as InvSvc
                except Exception:
                    InvSvc = None

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
                    # Use InventoryService for auditable stock deduction
                    if InvSvc:
                        InvSvc.deduct_stock(line['product'], line['qty'], order_ref, current_user.id)
                    else:
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
                    # Log voucher usage for audit trail
                    try:
                        from eacis.services import voucher_service as VchSvc
                    except Exception:
                        VchSvc = None
                    if VchSvc:
                        VchSvc.record_usage(voucher, current_user.id, order.id, voucher_discount)

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
            saved_addresses=saved_addresses,
        )

    @app.route('/customer/checkout/kyc', methods=['GET'])
    def customer_checkout_kyc():
        """Identity verification gate before installment checkout."""
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))
        if not session.get('pending_checkout'):
            flash('Please start your checkout first.', 'error')
            return redirect(url_for('checkout'))
        from datetime import date
        return render_template('customer/installment_kyc.html', today=date.today().isoformat())

    @app.route('/checkout/verify-identity', methods=['POST'])
    @app.route('/customer/checkout/verify-identity', methods=['POST'])
    def customer_checkout_verify_identity():
        """Process KYC form and set session flag."""
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False)):
            return redirect(url_for('auth_login'))
        errors = []
        id_type = (request.form.get('id_type') or '').strip()
        id_number = (request.form.get('id_number') or '').strip().replace('-', '').replace(' ', '')
        dob = (request.form.get('date_of_birth') or '').strip()
        auth_password = request.form.get('account_password') or ''
        certify = request.form.get('certify_accurate')
        data_use = request.form.get('agree_data_use')
        terms = request.form.get('agree_installment_terms')
        if not id_type:
            errors.append('Government ID type is required.')
        if not id_number or len(id_number) < 6:
            errors.append('A valid ID number (at least 6 characters) is required.')
        if not dob:
            errors.append('Date of birth is required.')
        if not auth_password or not current_user.check_password(auth_password):
            errors.append('Current account password is required to continue installment verification.')
        if not (certify and data_use and terms):
            errors.append('All declarations must be acknowledged.')
        if errors:
            from datetime import date
            for e in errors:
                flash(e, 'error')
            return render_template('customer/installment_kyc.html', today=date.today().isoformat())
        # Mark KYC as verified in session
        session['kyc_verified'] = True
        session['kyc_id_type'] = id_type
        session['kyc_verified_at'] = datetime.utcnow().isoformat()
        # Do NOT store actual ID number in session for security
        return redirect(url_for('customer_checkout_installment_confirm'))

    @app.route('/customer/checkout/installment-confirm', methods=['GET'])
    def customer_checkout_installment_confirm():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        pending = session.get('pending_checkout')
        if not pending:
            flash('No pending installment checkout found.', 'error')
            return redirect(url_for('checkout'))

        # Require fresh KYC before this step
        kyc_verified_at = session.get('kyc_verified_at')
        is_kyc_fresh = False
        if session.get('kyc_verified') and kyc_verified_at:
            try:
                verified_at = datetime.fromisoformat(str(kyc_verified_at))
                if verified_at.tzinfo is not None:
                    verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
                is_kyc_fresh = (datetime.utcnow() - verified_at).total_seconds() <= 900
            except Exception:
                is_kyc_fresh = False
        if not is_kyc_fresh:
            flash('Identity verification is required before confirming an installment plan.', 'error')
            return redirect(url_for('customer_checkout_kyc'))

        # If KYC is fresh, treat it as satisfying installment OTP requirement
        # to streamline flows where identity was just verified.
        try:
            if is_kyc_fresh and not is_installment_otp_fresh():
                session['installment_otp_verified'] = True
                session['installment_otp_verified_at'] = session.get('kyc_verified_at') or datetime.utcnow().isoformat()
        except Exception:
            # ignore and fall back to OTP flow
            pass

        if not is_installment_otp_fresh():
            challenge, otp_error = start_otp_flow(
                user=current_user,
                purpose='installment_confirm',
                next_url=url_for('customer_checkout_installment_confirm'),
                mode='checkout',
                meta={'flow': 'installment_checkout', 'order_total': float(pending.get('order_total') or 0), 'plan_months': int(pending.get('plan_months') or 0)},
            )
            if not challenge:
                flash(otp_error or 'Could not send installment verification code.', 'error')
                return redirect(url_for('checkout'))
            session['otp_message'] = 'Check your email to confirm this installment order.'
            return redirect(url_for('auth_otp_verify'))

        total = pending['order_total']
        months = pending['plan_months']
        monthly = round(total / months, 2) if months > 0 else total
        schedule = []
        today = datetime.utcnow().date()
        for i in range(months):
            schedule.append({'month': i + 1, 'due_date': today + timedelta(days=30 * (i + 1)), 'amount': monthly})

        return render_template('customer/checkout_installment_confirm.html',
                               total=total, months=months, monthly=monthly,
                               schedule=schedule, data=pending['data'])

    @app.route('/customer/checkout/success')
    def checkout_success():
        from flask_login import current_user
        order_ref = request.args.get('order_ref', '')
        if not order_ref:
            return redirect(url_for('customer_orders'))
        try:
            from .models.order import Order
        except Exception:
            from models.order import Order
        order = None
        ordered_items = []
        placed_at = None
        earned_points = 0
        if order_ref and current_user and current_user.is_authenticated:
            order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first()
            if order:
                ordered_items = list(order.items.all()) if order.items else []
                placed_at = order.created_at
                earned_points = int(order.total // 100) if order.total else 0
                # Clear KYC session flag after successful order
                session.pop('kyc_verified', None)
                session.pop('kyc_id_type', None)
                session.pop('pending_checkout', None)
                clear_installment_otp_session()
        if not order:
            flash('Order not found.', 'error')
            return redirect(url_for('customer_orders'))
        return render_template('customer/checkout_success.html',
                               order_ref=order_ref, order=order,
                               ordered_items=ordered_items, placed_at=placed_at,
                               earned_points=earned_points, estimated_delivery=None)

    # ── Order Cancellation ─────────────────────────────────────────────────
    @app.route('/customer/orders/<order_ref>/cancel', methods=['POST'])
    def customer_order_cancel(order_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.order import Order
        except Exception:
            from models.order import Order

        order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first()
        if not order:
            flash('Order not found.', 'error')
            return redirect(url_for('customer_orders'))

        cancellable = False
        if order.status == 'pending':
            cancellable = True
        elif order.status == 'paid' and order.paid_at:
            elapsed = (datetime.utcnow() - order.paid_at).total_seconds()
            cancellable = elapsed <= 3600

        if not cancellable:
            flash('This order cannot be cancelled at its current stage.', 'error')
            return redirect(url_for('customer_order_detail', order_ref=order_ref))

        if order.status == 'paid' and not is_order_cancel_otp_fresh():
            session['pending_order_cancel_ref'] = order_ref
            challenge, otp_error = start_otp_flow(
                user=current_user,
                purpose='order_cancel',
                next_url=url_for('customer_orders'),
                mode='checkout',
                meta={'flow': 'paid_order_cancellation', 'order_ref': order_ref},
            )
            if not challenge:
                clear_cancel_order_session()
                flash(otp_error or 'Could not send cancellation verification code.', 'error')
                return redirect(url_for('customer_order_detail', order_ref=order_ref))
            session['otp_message'] = 'Check your email to confirm this paid order cancellation.'
            return redirect(url_for('auth_otp_verify'))

        success, message = finalize_customer_order_cancel(current_user, order_ref)
        if success:
            clear_cancel_order_session()
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('customer_orders'))

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

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip()

        query = Order.query.filter(Order.customer_id == current_user.id)
        if q and len(q) >= 2:
            like_q = f"%{q}%"
            query = query.filter((Order.order_ref.ilike(like_q)) | (Order.notes.ilike(like_q)))
        if status_filter != 'all':
            query = query.filter(Order.status == status_filter)

        # Pagination: allow system-wide per-page choices (5 or 10)
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        orders = pagination.items

        # Return map for quick lookup (small set) remains the same
        return_map = {item.order_id: item for item in ReturnRequest.query.filter(ReturnRequest.customer_id == current_user.id).all()}

        # Compute stats from the full dataset (not only page items)
        total_count = Order.query.filter(Order.customer_id == current_user.id).count()
        pending_count = Order.query.filter(Order.customer_id == current_user.id, Order.status == 'pending').count()
        shipped_count = Order.query.filter(Order.customer_id == current_user.id, Order.status == 'shipped').count()
        delivered_count = Order.query.filter(Order.customer_id == current_user.id, Order.status == 'delivered').count()

        stats = {
            'total': total_count,
            'pending': pending_count,
            'shipped': shipped_count,
            'delivered': delivered_count,
        }
        return render_template('customer/orders.html', orders=orders, pagination=pagination, return_map=return_map, stats=stats, filters={'q': q, 'status': status_filter})

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

        # Prepare per-item review/star context maps for the template
        star_counts = {}
        starred_by_user_map = {}
        user_reviews_map = {}
        can_review_map = {}
        try:
            from eacis.models.product_star import ProductStar
            from eacis.models.review import Review
            from eacis.services.review_service import has_user_received_product

            from flask_login import current_user
            for item in order.items.all():
                pid = getattr(item, 'product_id', None)
                if not pid:
                    continue
                try:
                    star_counts[pid] = ProductStar.query.filter_by(product_id=pid).count()
                except Exception:
                    star_counts[pid] = 0
                try:
                    starred_by_user_map[pid] = bool(ProductStar.query.filter_by(product_id=pid, user_id=current_user.id).first())
                except Exception:
                    starred_by_user_map[pid] = False
                try:
                    user_reviews_map[pid] = Review.query.filter_by(product_id=pid, user_id=current_user.id).first()
                except Exception:
                    user_reviews_map[pid] = None
                try:
                    # prefer the robust helper; fall back to delivered-order check
                    can_review_map[pid] = bool(has_user_received_product(current_user.id, pid))
                except Exception:
                    can_review_map[pid] = (order.status == 'delivered')
        except Exception:
            # ignore failures and let template render without maps
            pass

        # Build cashflow timeline for display (payments, vouchers, installments, refunds)
        cashflow = []
        try:
            from eacis.models.voucher_usage import VoucherUsageLog
            from eacis.models.return_request import ReturnRequest as ReturnReqModel
            from eacis.models.refund_transaction import RefundTransaction
            from eacis.models.installment import InstallmentSchedule
        except Exception:
            try:
                from models.voucher_usage import VoucherUsageLog
                from models.return_request import ReturnRequest as ReturnReqModel
                from models.refund_transaction import RefundTransaction
                from models.installment import InstallmentSchedule
            except Exception:
                VoucherUsageLog = RefundTransaction = InstallmentSchedule = None
                ReturnReqModel = None

        # Payments and installment events
        try:
            if getattr(order, 'payment_method', '') == 'installment' and getattr(order, 'installment_plan', None):
                plan = order.installment_plan
                try:
                    down = float(getattr(plan, 'downpayment', 0) or 0)
                except Exception:
                    down = 0.0
                if down > 0:
                    ts = getattr(order, 'paid_at', None) or getattr(order, 'created_at', None)
                    cashflow.append({'ts': ts, 'kind': 'downpayment', 'label': 'Downpayment', 'amount': -down, 'method': getattr(order, 'payment_method', None), 'ref': None})

                try:
                    schedules = plan.schedules.order_by(InstallmentSchedule.due_date).all()
                except Exception:
                    schedules = list(getattr(plan, 'schedules', []) or [])

                for idx, sch in enumerate(schedules, start=1):
                    if getattr(sch, 'status', None) == 'paid':
                        ts = getattr(sch, 'paid_at', None) or (getattr(sch, 'due_date', None) and datetime.combine(getattr(sch, 'due_date'), datetime.min.time()))
                        cashflow.append({'ts': ts, 'kind': 'installment', 'label': f'Installment payment #{idx}', 'amount': -float(getattr(sch, 'amount', 0) or 0), 'method': getattr(sch, 'payment_ref', None), 'ref': getattr(sch, 'payment_ref', None)})
            else:
                if getattr(order, 'paid_at', None):
                    cashflow.append({'ts': order.paid_at, 'kind': 'payment', 'label': 'Payment received', 'amount': -float(getattr(order, 'total', 0) or 0), 'method': getattr(order, 'payment_method', None), 'ref': getattr(order, 'payment_ref', None)})
        except Exception:
            pass

        # Voucher usages (savings applied at checkout)
        try:
            if VoucherUsageLog:
                vlogs = VoucherUsageLog.query.filter_by(order_id=order.id).all()
                for v in vlogs:
                    try:
                        code = getattr(v.voucher, 'code', '')
                    except Exception:
                        code = ''
                    cashflow.append({'ts': getattr(v, 'used_at', None), 'kind': 'voucher', 'label': f'Voucher used ({code})', 'amount': float(getattr(v, 'discount_applied', 0) or 0), 'ref': None})
        except Exception:
            pass

        # Returns and refunds
        try:
            rrs = []
            if ReturnReqModel:
                rrs = ReturnReqModel.query.filter_by(order_id=order.id).all()
            for rr in rrs:
                cashflow.append({'ts': getattr(rr, 'created_at', None), 'kind': 'return_request', 'label': f'Return requested ({getattr(rr, "status", "")})', 'amount': 0, 'ref': getattr(rr, 'rrt_ref', None)})
                for rt in getattr(rr, 'refund_transactions', []) or []:
                    cashflow.append({'ts': getattr(rt, 'processed_at', None), 'kind': 'refund', 'label': f'Refund {getattr(rt, "refund_ref", "")}', 'amount': float(getattr(rt, 'amount', 0) or 0), 'method': getattr(rt, 'method', None), 'ref': getattr(rt, 'refund_ref', None), 'status': getattr(rt, 'status', None)})
        except Exception:
            pass

        # Sort events: newest first, keep undated at the end
        try:
            dated = [c for c in cashflow if c.get('ts')]
            undated = [c for c in cashflow if not c.get('ts')]
            cashflow = sorted(dated, key=lambda x: x['ts'], reverse=True) + undated
        except Exception:
            pass

        return render_template('customer/order_detail.html', order=order, existing_return=existing_return, today=datetime.utcnow().date(), star_counts=star_counts, starred_by_user_map=starred_by_user_map, user_reviews_map=user_reviews_map, can_review_map=can_review_map, cashflow=cashflow)

    @app.route('/customer/invoices')
    def customer_invoices():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.invoice import Invoice
        except Exception:
            from models.invoice import Invoice

        # Paginate invoices for customer
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = Invoice.query.filter_by(customer_id=current_user.id)
        pagination = base_q.order_by(Invoice.issued_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        invoices = pagination.items

        # page subtotal (grand_total) for quick reference
        page_total = sum(float(inv.grand_total or 0) for inv in invoices)

        return render_template('customer/invoices.html', invoices=invoices, pagination=pagination, page_total=page_total)

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

    @app.route('/customer/installments')
    @app.route('/customer/installment-payments')
    def customer_installments():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.installment import InstallmentPlan, InstallmentSchedule
            from .models.order import Order
        except Exception:
            from models.installment import InstallmentPlan, InstallmentSchedule
            from models.order import Order

        try:
            from eacis.services import installment_service as InstSvc
        except Exception:
            InstSvc = None

        if InstSvc:
            try:
                InstSvc.sync_overdue_schedules()
                db.session.commit()
            except Exception:
                db.session.rollback()

        plan_rows = (
            db.session.query(InstallmentPlan, Order)
            .join(Order, Order.id == InstallmentPlan.order_id)
            .filter(Order.customer_id == current_user.id)
            .order_by(InstallmentPlan.id.desc())
            .all()
        )

        plan_ids = [plan.id for plan, _ in plan_rows]
        schedules = InstallmentSchedule.query.filter(InstallmentSchedule.plan_id.in_(plan_ids)).all() if plan_ids else []
        today = datetime.utcnow().date()

        def effective_status(schedule):
            if schedule.status == 'paid':
                return 'paid'
            if schedule.status == 'past_due':
                return 'past_due'
            if schedule.due_date and schedule.due_date < today:
                return 'past_due'
            return 'pending'

        schedule_map = {}
        for row in schedules:
            row.effective_status = effective_status(row)
            schedule_map.setdefault(row.plan_id, []).append(row)

        installments = []
        total_outstanding = 0.0
        active_count = 0
        past_due_count = 0

        for plan, order in plan_rows:
            rows = schedule_map.get(plan.id, [])
            rows_sorted = sorted(rows, key=lambda r: (r.due_date or datetime.utcnow().date()))
            paid_rows = [r for r in rows_sorted if r.effective_status == 'paid']
            pending_rows = [r for r in rows_sorted if r.effective_status in ('pending', 'past_due')]
            next_due = pending_rows[0] if pending_rows else None
            outstanding = sum(float(r.amount or 0) for r in pending_rows)
            total_outstanding += outstanding

            if (plan.status or '') == 'active':
                active_count += 1
            if any(r.effective_status == 'past_due' for r in rows_sorted):
                past_due_count += 1

            installments.append({
                'plan': plan,
                'order': order,
                'schedules': rows_sorted,
                'paid_count': len(paid_rows),
                'remaining_count': len(pending_rows),
                'next_due': next_due,
                'outstanding': outstanding,
                'progress_pct': (len(paid_rows) / len(rows_sorted) * 100.0) if rows_sorted else 0.0,
            })

        stats = {
            'total': len(plan_rows),
            'active': active_count,
            'past_due': past_due_count,
            'outstanding': total_outstanding,
        }

        return render_template('customer/installments.html', installments=installments, stats=stats, today=today)

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
        return_form = {
            'order_ref': '',
            'reason': '',
            'description': '',
            'returns_consent': '',
            'terms_consent': '',
            'privacy_consent': ''
        }

        # Import return service for policy enforcement
        try:
            from eacis.services import return_service as RetSvc
        except Exception:
            RetSvc = None

        # ── Abuse restriction check ───────────────────────────────────────
        is_restricted = False
        if RetSvc and RetSvc.is_customer_restricted(current_user.id):
            is_restricted = True

        if request.method == 'POST':
            # Block if restricted
            if is_restricted:
                flash('Your account has been temporarily restricted from submitting new return requests. '
                      'Please contact support.', 'error')
                return redirect(url_for('customer_returns'))

            return_errors, return_data = validate_return_payload(request.form)
            return_form.update(return_data)
            order_ref = return_data.get('order_ref')
            reason_category = return_data.get('reason_category')
            description = return_data.get('description')
            item_condition = (request.form.get('item_condition') or '').strip() or None
            accepted_values = {'yes', 'on', 'true', '1'}
            terms_consent = (request.form.get('terms_consent') or '').strip().lower()
            privacy_consent = (request.form.get('privacy_consent') or '').strip().lower()
            returns_consent = (request.form.get('returns_consent') or '').strip().lower()

            return_form['terms_consent'] = 'yes' if terms_consent in accepted_values else ''
            return_form['privacy_consent'] = 'yes' if privacy_consent in accepted_values else ''
            return_form['returns_consent'] = 'yes' if returns_consent in accepted_values else ''
            evidence_link = (request.form.get('evidence_urls') or '').strip()
            other_reason = (request.form.get('other_reason') or '').strip()
            uploaded_evidence_files = [f for f in request.files.getlist('evidence_images') if f and f.filename]
            uploaded_evidence_paths = []

            order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first() if order_ref else None
            if order_ref and not order:
                return_errors['order_ref'] = 'Please choose one of your own orders.'

            # ── Policy eligibility check ──────────────────────────────────
            if not return_errors and order and RetSvc:
                eligible, elig_msg = RetSvc.validate_return_eligibility(order, current_user.id)
                if not eligible:
                    return_errors['order_ref'] = elig_msg

            # ── Evidence requirement check ────────────────────────────────
            if not return_errors and reason_category and RetSvc:
                if RetSvc.evidence_required(reason_category):
                    if not evidence_link and not uploaded_evidence_files:
                        return_errors['evidence'] = f'Photo evidence is required for {reason_category.replace("_", " ").title()} claims.'

            # Terms and privacy consent are both mandatory for return submissions.
            if not return_errors:
                has_terms = terms_consent in accepted_values
                has_privacy = privacy_consent in accepted_values
                if not (has_terms and has_privacy):
                    return_errors['returns_consent'] = 'Please accept both Terms and Conditions and Privacy Policy to continue.'

            if not return_errors and uploaded_evidence_files:
                for image_file in uploaded_evidence_files:
                    saved_path, upload_error = save_return_evidence(image_file, current_user.id)
                    if upload_error:
                        return_errors['evidence'] = upload_error
                        break
                    uploaded_evidence_paths.append(saved_path)

            if not return_errors:
                try:
                    evidence_payload = []
                    if evidence_link:
                        evidence_payload.append(evidence_link)
                    evidence_payload.extend(uploaded_evidence_paths)

                    # Use service to create the return request
                    rrt, msg = RetSvc.create_return_request(
                        customer_id=current_user.id,
                        order_id=order.id,
                        reason_category=reason_category,
                        description=description,
                        evidence_urls=evidence_payload,
                        other_reason=other_reason
                    )
                    
                    if rrt:
                        flash(msg, 'success')
                        return redirect(url_for('customer_returns'))
                    else:
                        return_errors['general'] = msg
                except Exception as e:
                    db.session.rollback()
                    return_errors['general'] = f'Could not submit return request: {str(e)}'
            else:
                flash('Please correct the highlighted return form fields.', 'error')

        # Orders for the select in the modal (limited set)
        orders = Order.query.filter(Order.customer_id == current_user.id).order_by(Order.created_at.desc()).limit(50).all()

        # Paginate return requests (allow per-page 5 or 10)
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = ReturnRequest.query.filter(ReturnRequest.customer_id == current_user.id)

        # compute stats from full set
        total_count = base_q.count()
        pending_count = base_q.filter(ReturnRequest.status == 'pending').count()
        accepted_count = base_q.filter(ReturnRequest.status == 'accepted').count()
        refunded_count = base_q.filter(ReturnRequest.status == 'refunded').count()

        pagination = base_q.order_by(ReturnRequest.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        returns = pagination.items
        abuse_score = RetSvc.get_customer_abuse_score(current_user.id) if RetSvc else 0
        latest_item = base_q.order_by(ReturnRequest.updated_at.desc()).first()
        latest_activity = (latest_item.updated_at or latest_item.created_at) if latest_item else None

        stats = {
            'total': total_count,
            'pending': pending_count,
            'accepted': accepted_count,
            'refunded': refunded_count,
        }

        return render_template('customer/returns.html', orders=orders, returns=returns, pagination=pagination, stats=stats, latest_activity=latest_activity, errors=return_errors, form=return_form, is_restricted=is_restricted, abuse_score=abuse_score)

    @app.route('/customer/inquiries', methods=['GET', 'POST'])
    def customer_inquiries():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from eacis.services import support_service as SupportSvc
        except Exception:
            SupportSvc = None
        from eacis.models.inquiry_ticket import InquiryTicket
        from eacis.models.order import Order

        inquiry_errors = {}
        inquiry_form = {}

        if request.method == 'POST':
            subject = request.form.get('subject', '').strip()
            category = request.form.get('category', 'OTHER').strip()
            description = request.form.get('description', '').strip()
            order_ref = request.form.get('order_ref', '').strip()
            
            inquiry_form = {'subject': subject, 'category': category, 'description': description, 'order_ref': order_ref}

            if not subject:
                inquiry_errors['subject'] = 'Please provide a brief subject for your inquiry.'
            if not description:
                inquiry_errors['description'] = 'Please describe your issue in detail.'
            
            if not inquiry_errors and SupportSvc:
                order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first() if order_ref else None
                if order_ref and not order:
                    inquiry_errors['order_ref'] = 'Invalid order reference.'

                if not inquiry_errors:
                    ticket = SupportSvc.create_ticket(
                        customer_id=current_user.id,
                        subject=f"[{category}] {subject}",
                        description=description,
                        order_id=order.id if order else None
                    )
                    if ticket:
                        flash(f'Inquiry {ticket.ticket_ref} submitted successfully.', 'success')
                        return redirect(url_for('customer_inquiries'))
                    else:
                        flash('Could not create support ticket. Please try again later.', 'error')
            elif not SupportSvc:
                flash('Support service unavailable.', 'error')
            else:
                flash('Please correct the highlighted fields in the support form.', 'error')

        # Orders used for the 'linked order' select in the modal (limit recent items)
        orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).limit(50).all()

        # Paginate tickets
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        ticket_query = InquiryTicket.query.filter_by(customer_id=current_user.id)
        pagination = ticket_query.order_by(InquiryTicket.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        tickets = pagination.items

        return render_template('customer/inquiries.html', tickets=tickets, orders=orders, pagination=pagination, errors=inquiry_errors, form=inquiry_form)

    @app.route('/customer/inquiries/<ticket_ref>', methods=['GET', 'POST'])
    def customer_inquiry_detail(ticket_ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from eacis.services import support_service as SupportSvc
        except Exception:
            SupportSvc = None
        from eacis.models.inquiry_ticket import InquiryTicket

        ticket = InquiryTicket.query.filter_by(ticket_ref=ticket_ref, customer_id=current_user.id).first()
        if not ticket:
            flash('Inquiry not found.', 'error')
            return redirect(url_for('customer_inquiries'))

        if request.method == 'POST':
            body = request.form.get('body', '').strip()
            if body and SupportSvc:
                SupportSvc.add_reply(ticket.id, current_user.id, body)
                flash('Reply sent.', 'success')
                return redirect(url_for('customer_inquiry_detail', ticket_ref=ticket_ref))

        return render_template('customer/inquiry_detail.html', ticket=ticket)

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

        transactions = LoyaltyTransaction.query.filter_by(user_id=current_user.id).order_by(LoyaltyTransaction.created_at.desc()).limit(30).all()
        active_vouchers = Voucher.query.filter(Voucher.is_active.is_(True)).order_by(Voucher.id.desc()).limit(30).all()

        claimed_voucher_ids = set()
        for order in Order.query.filter_by(customer_id=current_user.id).filter(Order.voucher_id.isnot(None)).all():
            claimed_voucher_ids.add(order.voucher_id)

        voucher_cards = []
        now = datetime.utcnow()
        for voucher in active_vouchers:
            if not voucher.is_valid():
                continue
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

        # Avoid loading full order history into memory: use counts and a small recent list
        try:
            from sqlalchemy import func
        except Exception:
            func = None

        base_q = Order.query.filter_by(customer_id=current_user.id)
        total_orders = base_q.count()
        recent_orders = base_q.order_by(Order.created_at.desc()).limit(5).all()
        returns_count = ReturnRequest.query.filter_by(customer_id=current_user.id).count()
        pending_count = base_q.filter(Order.status.in_(['pending', 'paid', 'packed', 'shipped'])).count()
        delivered_count = base_q.filter(Order.status == 'delivered').count()

        # Compute total_spent using DB aggregation when possible
        total_spent = 0.0
        try:
            if func is not None:
                total_spent_val = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(Order.customer_id == current_user.id, Order.status.in_(['paid', 'packed', 'shipped', 'delivered', 'refunded'])).scalar()
                total_spent = float(total_spent_val or 0)
        except Exception:
            total_spent = sum(float(order.total or 0) for order in recent_orders if order.status in ('paid', 'packed', 'shipped', 'delivered', 'refunded'))

        profile_stats = {
            'total_orders': total_orders,
            'pending_orders': pending_count,
            'delivered_orders': delivered_count,
            'returns': returns_count,
            'total_spent': total_spent,
        }
        profile_checks = [
            ('First name', bool(current_user.first_name)),
            ('Last name', bool(current_user.last_name)),
            ('Mobile number', bool(current_user.phone)),
            ('Address line', bool(current_user.address_line1)),
            ('City/Municipality', bool(current_user.city_municipality)),
            ('Province', bool(current_user.province)),
            ('Postal code', bool(current_user.postal_code)),
        ]
        completed_fields = sum(1 for _, is_done in profile_checks if is_done)
        profile_completion = int(round((completed_fields / len(profile_checks)) * 100)) if profile_checks else 0
        missing_profile_fields = [label for label, is_done in profile_checks if not is_done]

        return render_template(
            'customer/profile.html',
            profile_stats=profile_stats,
            recent_orders=recent_orders,
            profile_completion=profile_completion,
            missing_profile_fields=missing_profile_fields,
        )

    @app.route('/customer/profile/edit', methods=['GET', 'POST'])
    def customer_profile_edit():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        pending_email_change = (session.get('pending_email_change_email') or '').strip().lower()

        if request.method == 'POST':
            profile_errors, profile_data = validate_profile_payload(request.form, postal_lookup)
            requested_email = (request.form.get('email') or '').strip().lower()
            current_password = request.form.get('current_password') or ''
            terms_consent = request.form.get('terms_consent') == 'yes'
            privacy_consent = request.form.get('privacy_consent') == 'yes'

            profile_data['email'] = requested_email or current_user.email or ''

            if not current_password:
                profile_errors['current_password'] = 'Enter your current password to save account changes.'
            elif not current_user.check_password(current_password):
                profile_errors['current_password'] = 'Current password is incorrect.'

            if not requested_email:
                profile_errors['email'] = 'Email address is required.'
            elif not EMAIL_PATTERN.match(requested_email):
                profile_errors['email'] = 'Please enter a valid email address.'
            elif requested_email != current_user.email and User.query.filter(User.email == requested_email, User.id != current_user.id).first():
                profile_errors['email'] = 'An account with this email already exists.'

            if not terms_consent:
                profile_errors['terms_consent'] = 'You must accept the Terms of Service before saving.'
            if not privacy_consent:
                profile_errors['privacy_consent'] = 'You must accept the Privacy Policy before saving.'

            if profile_errors:
                profile_data['terms_consent'] = terms_consent
                profile_data['privacy_consent'] = privacy_consent
                return render_template('customer/profile_edit.html', errors=profile_errors, form=profile_data)

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
            # Avatar removal (checkbox/hide) and upload handling
            try:
                if request.form.get('remove_profile_image') == '1':
                    try:
                        _remove_avatar_files('customer', current_user.id)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                upload = request.files.get('profile_image') if hasattr(request, 'files') else None
                if upload and getattr(upload, 'filename', None):
                    ok, err = _save_avatar(upload, 'customer', current_user.id)
                    if not ok:
                        profile_errors['profile_image'] = err or 'Could not save uploaded image.'
                        profile_data['terms_consent'] = terms_consent
                        profile_data['privacy_consent'] = privacy_consent
                        return render_template('customer/profile_edit.html', errors=profile_errors, form=profile_data)
            except Exception:
                pass
            try:
                db.session.commit()
                if requested_email and requested_email != current_user.email:
                    old_email = current_user.email
                    challenge, otp_error = start_otp_flow(
                        user=current_user,
                        purpose='email_change',
                        next_url=url_for('customer_profile_edit'),
                        mode='profile',
                        meta={'flow': 'profile_email_change', 'old_email': old_email, 'requested_email': requested_email},
                        email_override=requested_email,
                    )
                    if not challenge:
                        flash(otp_error or 'Profile saved, but we could not send an email verification code.', 'error')
                        clear_email_change_session()
                        return redirect(url_for('customer_profile_edit'))
                    session['pending_email_change_email'] = requested_email
                    session['pending_email_change_user_id'] = current_user.id
                    session['pending_email_change_old_email'] = old_email
                    session['otp_message'] = 'Check your new email address to verify this change.'
                    flash('Profile saved. We sent a verification code to your new email address.', 'success')
                    return redirect(url_for('auth_otp_verify'))
                flash('Profile updated.', 'success')
                return redirect(url_for('customer_profile'))
            except Exception:
                db.session.rollback()
                profile_errors = {'general': 'Could not update profile.'}
                return render_template('customer/profile_edit.html', errors=profile_errors, form=profile_data)

        form_data = {
            'first_name': current_user.first_name or '',
            'middle_name': current_user.middle_name or '',
            'last_name': current_user.last_name or '',
            'suffix': current_user.suffix or '',
            'email': pending_email_change or current_user.email or '',
            'phone': current_user.phone or '',
            'address_line1': current_user.address_line1 or '',
            'address_line2': current_user.address_line2 or '',
            'barangay': current_user.barangay or '',
            'city_municipality': current_user.city_municipality or '',
            'province': current_user.province or '',
            'region': current_user.region or '',
            'postal_code': current_user.postal_code or '',
            'terms_consent': False,
            'privacy_consent': False,
        }
        return render_template('customer/profile_edit.html', errors={}, form=form_data)

    @app.route('/customer/security', methods=['GET', 'POST'])
    def customer_security():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
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
                return render_template('customer/security.html', errors=errors, form=form_data)

            if not is_customer_security_otp_fresh():
                challenge, otp_error = start_otp_flow(
                    user=current_user,
                    purpose='customer_security',
                    next_url=url_for('customer_security'),
                    mode='profile',
                    meta={'flow': 'customer_security_password_change'},
                )
                if not challenge:
                    errors = {'general': otp_error or 'Could not send security verification code.'}
                    return render_template('customer/security.html', errors=errors, form=form_data)
                session['otp_message'] = 'Check your email to confirm this security change.'
                return redirect(url_for('auth_otp_verify'))

            try:
                current_user.set_password(form_data['new_password'])
                db.session.commit()
                try:
                    try:
                        from .models.audit import AuditLog
                    except Exception:
                        from models.audit import AuditLog
                    try:
                        db.session.add(AuditLog(
                            actor_id=current_user.id,
                            actor_name=getattr(current_user, 'full_name', None) or current_user.email,
                            role=current_user.role,
                            action='password_changed',
                            module='security',
                            target_ref=current_user.email,
                            meta={'context': 'customer_security'},
                            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                        ))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                except Exception:
                    try:
                        app.logger.exception('Failed to record customer password change audit')
                    except Exception:
                        pass
                clear_customer_security_session()
                flash('Password updated.', 'success')
            except Exception:
                db.session.rollback()
                errors = {'general': 'Could not update password right now.'}
                return render_template('customer/security.html', errors=errors, form=form_data)
            return redirect(url_for('customer_profile'))

        return render_template('customer/security.html', errors=errors, form=form_data)

    @app.route('/customer/addresses', methods=['GET', 'POST'])
    def customer_addresses():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.address import Address
        except Exception:
            from models.address import Address

        errors = {}
        form = {}

        if request.method == 'POST':
            action = (request.form.get('action') or 'save').strip()
            # Save new address
            if action == 'save':
                form = dict(request.form)
                recipient_name = (request.form.get('recipient_name') or '').strip()
                address_line1 = (request.form.get('address_line1') or '').strip()
                phone_raw = (request.form.get('phone') or '').strip()
                phone_norm = normalize_phone(phone_raw) if phone_raw else None

                if not recipient_name:
                    errors['recipient_name'] = 'Recipient name is required.'
                if not address_line1:
                    errors['address_line1'] = 'Address is required.'

                if errors:
                    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
                    return render_template('customer/addresses.html', addresses=addresses, errors=errors, form=form)

                is_default = bool(request.form.get('set_default'))
                try:
                    new_addr = Address(
                        user_id=current_user.id,
                        label=(request.form.get('label') or '').strip(),
                        recipient_name=recipient_name,
                        phone=phone_norm,
                        address_line1=address_line1,
                        address_line2=(request.form.get('address_line2') or '').strip(),
                        barangay=(request.form.get('barangay') or '').strip(),
                        city_municipality=(request.form.get('city_municipality') or '').strip(),
                        province=(request.form.get('province') or '').strip(),
                        region=(request.form.get('region') or '').strip(),
                        postal_code=(request.form.get('postal_code') or '').strip(),
                        is_default=is_default,
                    )
                    if is_default:
                        Address.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
                    db.session.add(new_addr)
                    db.session.commit()
                    flash('Address saved.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not save address. Try again.', 'error')
                return redirect(url_for('customer_addresses'))

            if action == 'set_default':
                try:
                    addr_id = int(request.form.get('address_id') or 0)
                    addr = Address.query.get(addr_id)
                    if addr and addr.user_id == current_user.id:
                        Address.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
                        addr.is_default = True
                        db.session.commit()
                        flash('Default address updated.', 'success')
                except Exception:
                    db.session.rollback()
                return redirect(url_for('customer_addresses'))

            if action == 'delete':
                try:
                    addr_id = int(request.form.get('address_id') or 0)
                    addr = Address.query.get(addr_id)
                    if addr and addr.user_id == current_user.id:
                        db.session.delete(addr)
                        db.session.commit()
                        flash('Address deleted.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not delete address.', 'error')
                return redirect(url_for('customer_addresses'))

        # Paginate addresses (small pages) so UI remains responsive for many addresses
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc())
        pagination = base_q.paginate(page=page, per_page=per_page, error_out=False)
        addresses = pagination.items
        return render_template('customer/addresses.html', addresses=addresses, pagination=pagination, errors=errors, form=form)
    @app.route('/customer/profile/trusted-devices', methods=['GET', 'POST'])
    def customer_trusted_devices():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        from eacis.services.trusted_device_service import list_trusted_devices, revoke_by_id

        if request.method == 'POST':
            revoke_id = request.form.get('revoke_id')
            if revoke_id:
                ok = revoke_by_id(current_user.id, revoke_id)
                if ok:
                    flash('Trusted device revoked.', 'success')
                    resp = redirect(url_for('customer_trusted_devices'))
                    cookie_name = app.config.get('TRUSTED_DEVICE_COOKIE_NAME', 'trusted_device')
                    resp.set_cookie(cookie_name, '', expires=0, path='/')
                    return resp
                else:
                    flash('Device not found or unauthorized.', 'error')
                    return redirect(url_for('customer_trusted_devices'))

        devices = list_trusted_devices(current_user.id)
        return render_template('customer/trusted_devices.html', devices=devices)

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

    @app.route('/cookies')
    def cookies():
        return render_template('cookie_policy.html')

    @app.route('/refunds')
    def refunds():
        return render_template('refund_policy.html')

    @app.route('/support')
    def support():
        from flask_login import current_user
        recent_tickets = []
        recent_returns = []
        
        if current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer':
            try:
                from .models.inquiry_ticket import InquiryTicket
                from .models.return_request import ReturnRequest
            except Exception:
                from models.inquiry_ticket import InquiryTicket
                from models.return_request import ReturnRequest
                
            recent_tickets = InquiryTicket.query.filter_by(customer_id=current_user.id).order_by(InquiryTicket.updated_at.desc()).limit(2).all()
            recent_returns = ReturnRequest.query.filter_by(customer_id=current_user.id).order_by(ReturnRequest.created_at.desc()).limit(2).all()
            
        return render_template('customer/support.html', recent_tickets=recent_tickets, recent_returns=recent_returns)

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

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip()
        query = Product.query.filter(Product.seller_id == current_user.id)
        if q and len(q) >= 2:
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

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        stats = {
            'total': Product.query.filter(Product.seller_id == current_user.id).count(),
            'active': Product.query.filter(Product.seller_id == current_user.id, Product.is_active.is_(True)).count(),
            'low_stock': Product.query.filter(Product.seller_id == current_user.id, Product.stock <= Product.low_stock_threshold).count(),
            'installment_enabled': Product.query.filter(Product.seller_id == current_user.id, Product.installment_enabled.is_(True)).count(),
        }
        return render_template('seller/products.html', products=pagination.items, pagination=pagination, stats=stats, filters={'q': q, 'status': status_filter})

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
        try:
            from .models.product_image import ProductImage
        except Exception:
            from models.product_image import ProductImage

        images = []
        if product and product_images_table_exists():
            try:
                images = ProductImage.query.filter_by(product_id=product.id).order_by(ProductImage.position.asc()).all()
            except Exception:
                images = []
        return render_template('seller/product_form.html', ref=ref, product=product, images=images, errors={}, form={})

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

    @app.route('/seller/products/<ref>/images/upload', methods=['POST'])
    def seller_product_image_upload(ref):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
            from .models.product_image import ProductImage
        except Exception:
            from models.product import Product
            from models.product_image import ProductImage

        product = Product.query.filter_by(product_ref=ref, seller_id=current_user.id).first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('seller_products'))

        file = None
        if request.files:
            # Accept single file under any field name
            file = next((f for f in request.files.values()), None)
        # optional debug: print request.files info when enabled in config
        try:
            if app.config.get('DEBUG_UPLOADS'):
                print('DEBUG_UPLOADS: request.files keys=', list(request.files.keys()))
                print('DEBUG_UPLOADS: file obj type=', type(file), 'filename=', getattr(file, 'filename', None))
        except Exception:
            pass

        if not file or not getattr(file, 'filename', None):
            if app.config.get('DEBUG_UPLOADS'):
                return jsonify({'status': 'no_image_uploaded'}), 400
            flash('No image uploaded.', 'error')
            return redirect(url_for('seller_product_detail', ref=ref))

        from werkzeug.utils import secure_filename
        import os, time, uuid

        allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in allowed_ext:
            if app.config.get('DEBUG_UPLOADS'):
                return jsonify({'status': 'unsupported_file_type', 'ext': ext}), 400
            flash('Unsupported file type. Allowed: png, jpg, jpeg, gif, webp', 'error')
            return redirect(url_for('seller_product_detail', ref=ref))

        existing = 0
        if product_images_table_exists():
            try:
                existing = ProductImage.query.filter_by(product_id=product.id).count()
            except Exception:
                existing = 0
        if existing >= 3:
            if app.config.get('DEBUG_UPLOADS'):
                return jsonify({'status': 'max_images_reached'}), 400
            flash('Maximum of 3 product images allowed.', 'error')
            return redirect(url_for('seller_product_detail', ref=ref))

        upload_dir = os.path.join(app.instance_path, 'uploads', 'products', product.product_ref)
        os.makedirs(upload_dir, exist_ok=True)
        unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(upload_dir, unique_name)
        try:
            file.save(save_path)
        except Exception:
            # Log exception for diagnostics and optionally print traceback when debugging
            try:
                app.logger.exception('Failed to save uploaded product image')
            except Exception:
                pass
            try:
                import traceback
                if app.config.get('DEBUG_UPLOADS'):
                    traceback.print_exc()
            except Exception:
                pass
            flash('Failed to save uploaded file.', 'error')
            return redirect(url_for('seller_product_detail', ref=ref))

        pos = existing + 1
        image = ProductImage(product_id=product.id, filename=unique_name, position=pos)
        try:
            if product_images_table_exists():
                db.session.add(image)
                db.session.commit()
                # when debugging uploads, return JSON with details instead of redirecting
                if app.config.get('DEBUG_UPLOADS'):
                    try:
                        return jsonify({'status': 'ok', 'saved_path': save_path, 'filename': unique_name, 'db_saved': True})
                    except Exception:
                        # fall through to normal behavior if jsonify fails
                        pass
                flash('Image uploaded.', 'success')
            else:
                # Table doesn't exist yet; file saved but DB record cannot be created
                flash('Image saved to disk but database migration not applied. Run migrations to register images.', 'warning')
        except Exception:
            # If DB write fails, remove the saved file to avoid orphaned files on disk
            try:
                if os.path.exists(save_path):
                    os.remove(save_path)
            except Exception:
                pass
            db.session.rollback()
            flash('Unable to save image record.', 'error')
        return redirect(url_for('seller_product_detail', ref=ref))

    @app.route('/seller/products/<ref>/images/<int:image_id>/delete', methods=['POST'])
    def seller_product_image_delete(ref, image_id):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))
        try:
            from .models.product import Product
            from .models.product_image import ProductImage
        except Exception:
            from models.product import Product
            from models.product_image import ProductImage

        if not product_images_table_exists():
            flash('Image management is unavailable: database table not found. Run migrations.', 'error')
            return redirect(url_for('seller_products'))

        image = ProductImage.query.get(image_id)
        if not image:
            flash('Image not found.', 'error')
            return redirect(url_for('seller_products'))

        product = Product.query.get(image.product_id)
        if not product or product.product_ref != ref or product.seller_id != current_user.id:
            flash('Permission denied.', 'error')
            return redirect(url_for('seller_products'))

        file_path = os.path.join(app.instance_path, 'uploads', 'products', product.product_ref, image.filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

        try:
            db.session.delete(image)
            # reindex positions
            try:
                remaining = ProductImage.query.filter_by(product_id=product.id).order_by(ProductImage.position).all()
                for idx, img in enumerate(remaining, start=1):
                    img.position = idx
            except Exception:
                # if reindex fails, ignore but continue
                pass
            db.session.commit()
            flash('Image deleted.', 'success')
        except Exception:
            db.session.rollback()
            flash('Unable to delete image.', 'error')
        return redirect(url_for('seller_product_detail', ref=ref))

    @app.route('/seller/inventory')
    def seller_inventory():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from eacis.services import inventory_service as InvSvc
        except Exception:
            InvSvc = None

        summary = InvSvc.get_inventory_summary(current_user.id) if InvSvc else {
            'total_stock_value': 0, 'out_of_stock_count': 0, 'low_stock_count': 0, 
            'movement_count_30d': 0, 'total_products': 0, 'low_stock_items': []
        }
        
        return render_template('seller/inventory.html', stats=summary, low_stock_items=summary.get('low_stock_items', []))

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

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip()
        date_filter = (request.args.get('date_filter') or '').strip()


        # Build a base query for Orders that include products from this seller
        base_q = Order.query.join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct()

        if q and len(q) >= 2:
            like_q = f"%{q}%"
            try:
                from .models.user import User
            except Exception:
                from models.user import User
            base_q = base_q.filter((Order.order_ref.ilike(like_q)) | (Order.customer.has(User.full_name.ilike(like_q))) | (Order.customer.has(User.email.ilike(like_q))))

        if status_filter != 'all':
            base_q = base_q.filter(Order.status == status_filter)
        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, '%Y-%m-%d')
                next_day = date_obj + timedelta(days=1)
                base_q = base_q.filter(Order.created_at >= date_obj, Order.created_at < next_day)
            except ValueError:
                pass

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)

        # Compute counts and paginate directly from base_q
        total_count = base_q.count()
        if total_count:
            pending_count = base_q.filter(Order.status == 'pending').count()
            shipped_count = base_q.filter(Order.status == 'shipped').count()
            delivered_count = base_q.filter(Order.status == 'delivered').count()

            pagination = base_q.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
            orders = pagination.items
            stats = {
                'total': total_count,
                'pending': pending_count,
                'shipped': shipped_count,
                'delivered': delivered_count,
            }
        else:
            pagination = None
            orders = []
            stats = {'total': 0, 'pending': 0, 'shipped': 0, 'delivered': 0}

        return render_template('seller/orders.html', orders=orders, pagination=pagination, stats=stats, filters={'q': q, 'status': status_filter, 'date_filter': date_filter})

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
                    # Sellers may only transition a safe subset of statuses.
                    allowed = ('packed', 'shipped', 'delivered')
                    if new_status not in allowed:
                        flash('Invalid or unauthorized order status change.', 'error')
                    else:
                        try:
                            # Gather distinct seller ids for items on this order
                            seller_ids = set()
                            for item in order.items.all():
                                if item.product and getattr(item.product, 'seller_id', None) is not None:
                                    try:
                                        seller_ids.add(int(item.product.seller_id))
                                    except Exception:
                                        seller_ids.add(item.product.seller_id)

                            # Prevent global 'shipped' or 'delivered' for multi-seller orders
                            if len(seller_ids) > 1 and new_status in ('shipped', 'delivered'):
                                flash('Cannot mark multi-seller order as shipped/delivered. Please coordinate with admin.', 'error')
                            else:
                                # If marking delivered, ensure this seller owns all items (safety check)
                                from flask_login import current_user
                                if new_status == 'delivered' and any(
                                    (item.product and int(item.product.seller_id or 0) != int(current_user.id))
                                    for item in order.items.all()
                                ):
                                    flash('Only the seller owning all items may mark the order as delivered.', 'error')
                                else:
                                    order.status = new_status
                                    if new_status == 'shipped' and not order.shipped_at:
                                        order.shipped_at = datetime.utcnow()
                                    elif new_status == 'delivered' and not order.delivered_at:
                                        order.delivered_at = datetime.utcnow()
                                    if new_status == 'shipped' and not order.tracking_number:
                                        order.tracking_number = f'TRK-{order.order_ref[-6:]}'
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

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip()

        query = ReturnRequest.query.join(OrderItem, OrderItem.order_id == ReturnRequest.order_id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id)
        if q and len(q) >= 2:
            like_q = f"%{q}%"
            query = query.filter((ReturnRequest.rrt_ref.ilike(like_q)) | (ReturnRequest.reason.ilike(like_q)) | (ReturnRequest.description.ilike(like_q)))
        if status_filter != 'all':
            query = query.filter(ReturnRequest.status == status_filter)

        # Paginate seller return requests
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = query

        total_count = base_q.distinct().count()
        pending_count = base_q.filter(ReturnRequest.status == 'pending').distinct().count()
        accepted_count = base_q.filter(ReturnRequest.status == 'accepted').distinct().count()
        refunded_count = base_q.filter(ReturnRequest.status == 'refunded').distinct().count()

        pagination = base_q.order_by(ReturnRequest.created_at.desc()).distinct().paginate(page=page, per_page=per_page, error_out=False)
        returns = pagination.items

        stats = {
            'total': total_count,
            'pending': pending_count,
            'accepted': accepted_count,
            'refunded': refunded_count,
        }
        return render_template('seller/returns.html', returns=returns, pagination=pagination, stats=stats, filters={'q': q, 'status': status_filter})

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

        # Import return service
        try:
            from eacis.services import return_service as RetSvc
        except Exception:
            RetSvc = None
        
        if not RetSvc:
            flash('Return service unavailable. Contact admin.', 'error')
            return redirect(url_for('seller_returns'))

        if action in ['approve', 'deny']:
            target_status = 'accepted' if action == 'approve' else 'rejected'
            success, msg = RetSvc.update_return_status(return_request.id, target_status, notes)
            if success:
                flash(f"Return {rrt_ref} {target_status}.", 'success')
            else:
                flash(msg, 'error')
        elif action == 'refund':
            if not is_seller_refund_otp_fresh():
                session['pending_seller_refund_rrt_ref'] = rrt_ref
                challenge, otp_error = start_otp_flow(
                    user=current_user,
                    purpose='seller_refund',
                    next_url=url_for('seller_returns'),
                    mode='profile',
                    meta={'flow': 'seller_refund_processing', 'rrt_ref': rrt_ref},
                )
                if not challenge:
                    clear_seller_refund_session()
                    flash(otp_error or 'Could not send refund verification code.', 'error')
                    return redirect(url_for('seller_returns'))
                session['otp_message'] = 'Check your email to confirm this refund.'
                return redirect(url_for('auth_otp_verify'))

            success, msg = finalize_seller_refund(current_user, rrt_ref)
            if success:
                clear_seller_refund_session()
                flash(msg, 'success')
            else:
                flash(msg, 'error')

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

        # Paginate vouchers and compute stats from the full set
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)

        base_q = Voucher.query.filter((Voucher.seller_id == current_user.id) | (Voucher.seller_id.is_(None)))

        # summary stats computed via DB aggregates where possible
        try:
            from sqlalchemy import func
            seller_filter = ((Voucher.seller_id == current_user.id) | (Voucher.seller_id.is_(None)))
            active_count = base_q.filter(Voucher.is_active.is_(True)).count()
            expiring_count = base_q.filter(Voucher.valid_until.isnot(None), Voucher.valid_until <= datetime.utcnow() + timedelta(days=7)).count()
            redemptions_total = int(db.session.query(func.coalesce(func.sum(func.coalesce(Voucher.uses_count, 0)), 0)).filter(seller_filter).scalar() or 0)
            discount_total = float(db.session.query(func.coalesce(func.sum(func.coalesce(Voucher.discount_value, 0) * func.coalesce(Voucher.uses_count, 0)), 0)).filter(seller_filter).scalar() or 0.0)
        except Exception:
            # Fallback: iterate when SQL functions aren't available
            rows = base_q.order_by(Voucher.id.desc()).all()
            active_count = sum(1 for row in rows if row.is_active)
            expiring_count = sum(1 for row in rows if row.valid_until and row.valid_until <= datetime.utcnow() + timedelta(days=7))
            redemptions_total = sum(int(row.uses_count or 0) for row in rows)
            discount_total = sum(float((row.discount_value or 0) * (row.uses_count or 0)) for row in rows)

        pagination = base_q.order_by(Voucher.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        vouchers = pagination.items

        stats = {
            'active': active_count,
            'redemptions_today': redemptions_total,
            'discount_total': discount_total,
            'expiring_soon': expiring_count,
        }

        return render_template('seller/vouchers.html', vouchers=vouchers, pagination=pagination, stats=stats)

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
            from eacis.services import analytics_service as AnaSvc
        except Exception:
            AnaSvc = None

        metrics = AnaSvc.get_financial_metrics(seller_id=current_user.id) if AnaSvc else {}
        
        return render_template('seller/financial_analytics.html', stats=metrics, batches=metrics.get('daily_series', []))

    @app.route('/seller/installment-payments')
    @app.route('/seller/installments')
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

        try:
            from .services import installment_service as InstSvc
        except Exception:
            try:
                from services import installment_service as InstSvc
            except Exception:
                InstSvc = None

        if InstSvc:
            try:
                InstSvc.sync_overdue_schedules()
                db.session.commit()
            except Exception:
                db.session.rollback()

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

    @app.route('/seller/installment-payments/<int:schedule_id>/mark-paid', methods=['POST'])
    def seller_installment_mark_paid(schedule_id):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'seller'):
            return redirect(url_for('auth_login', next=request.path))

        from eacis.models.installment import InstallmentSchedule, InstallmentPlan
        from eacis.models.order import OrderItem
        from eacis.models.product import Product
        try:
            from eacis.services import installment_service as InstSvc
        except Exception:
            InstSvc = None

        schedule = InstallmentSchedule.query.get(schedule_id)
        if not schedule:
            flash('Installment schedule not found.', 'error')
            return redirect(url_for('seller_installment_payments'))

        plan = InstallmentPlan.query.get(schedule.plan_id)
        if not plan:
            flash('Installment plan not found.', 'error')
            return redirect(url_for('seller_installment_payments'))

        # Ensure this seller actually owns at least one order line in the schedule's order.
        seller_owns_order = (
            db.session.query(OrderItem.id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(OrderItem.order_id == plan.order_id, Product.seller_id == current_user.id)
            .first()
            is not None
        )
        if not seller_owns_order:
            flash('You do not have permission to update this installment schedule.', 'error')
            return redirect(url_for('seller_installment_payments'))

        payment_ref = (request.form.get('payment_ref') or '').strip()
        ok, message = InstSvc.record_payment(schedule_id=schedule_id, payment_ref=payment_ref, actor_id=current_user.id)
        if not ok:
            flash(message, 'error')
            return redirect(url_for('seller_installment_payments'))

        try:
            db.session.commit()
            flash('Installment payment recorded.', 'success')
        except Exception:
            db.session.rollback()
            flash('Unable to record installment payment right now.', 'error')
        return redirect(url_for('seller_installment_payments'))

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
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = query
        pagination = base_q.order_by(InquiryTicket.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        tickets = pagination.items

        stats = {
            'open': base_q.filter(InquiryTicket.status == 'open').count(),
            'in_progress': base_q.filter(InquiryTicket.status == 'in_progress').count(),
            'resolved': base_q.filter(InquiryTicket.status.in_(['resolved', 'closed'])).count(),
        }
        return render_template('seller/customer_inquiries.html', tickets=tickets, pagination=pagination, stats=stats, status_filter=status_filter)

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
            from .models.inquiry_reply import InquiryReply
        except Exception:
            from models.inquiry_ticket import InquiryTicket
            from models.inquiry_reply import InquiryReply

        ticket = InquiryTicket.query.filter_by(ticket_ref=ticket_ref).first()
        if not ticket:
            flash('Inquiry not found.', 'error')
            return redirect(url_for('seller_customer_inquiries'))

        if request.method == 'POST':
            try:
                from eacis.services import support_service as SupportSvc
            except Exception:
                SupportSvc = None

            action = request.form.get('action', 'reply')
            if action == 'update_status' and SupportSvc:
                new_status = request.form.get('status', ticket.status)
                if new_status in ('resolved', 'closed'):
                    SupportSvc.resolve_ticket(ticket.id, current_user.id)
                else:
                    ticket.status = new_status
                    db.session.commit()
                flash('Status updated.', 'success')
            elif SupportSvc:
                body = request.form.get('body', '').strip()
                is_internal = request.form.get('is_internal') == 'true'
                if body:
                    SupportSvc.add_reply(ticket.id, current_user.id, body, is_internal=is_internal)
                    # Also ensure ticket is assigned to the replying seller
                    ticket.assigned_to = current_user.id
                    db.session.commit()
                    flash(f'{"Internal note" if is_internal else "Reply"} sent.', 'success')
            
            return redirect(url_for('seller_inquiry_detail', ticket_ref=ticket_ref))

        return render_template('seller/inquiry_detail.html', ticket=ticket)

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
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = Invoice.query.filter_by(seller_id=current_user.id)
        pagination = base_q.order_by(Invoice.issued_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        invoices = pagination.items
        page_total = sum(float(inv.grand_total or 0) for inv in invoices)

        return render_template('seller/invoices.html', invoices=invoices, pagination=pagination, page_total=page_total)

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
            from eacis.services import inventory_service as InvSvc
        except Exception:
            InvSvc = None

        summary = InvSvc.get_inventory_summary(current_user.id) if InvSvc else {}

        # Ensure the template has the expected keys to avoid UndefinedError
        expected = {
            'avg_coverage_days': None,
            'sell_through_rate': 0.0,
            'aging_skus_count': 0,
            'out_of_stock_count': 0,
            'top_products': [],
            'low_stock_items': [],
        }
        if not isinstance(summary, dict):
            try:
                summary = dict(summary)
            except Exception:
                summary = {}

        for k, v in expected.items():
            summary.setdefault(k, v)

        # Coerce falsy list-like values to empty lists for template slicing
        if not summary.get('top_products'):
            summary['top_products'] = []
        if not summary.get('low_stock_items'):
            summary['low_stock_items'] = []

        return render_template('seller/inventory_analytics.html', stats=summary)

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

        # Build a base query for orders that include products from this seller
        base_q = Order.query.join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct()

        # Compute summary stats from the base query (avoids loading all rows into memory)
        try:
            in_transit = base_q.filter(Order.status == 'shipped').count()
            delivered_count = base_q.filter(Order.status == 'delivered').count()
            failed = base_q.filter(Order.status == 'cancelled').count()

            # Fetch delivered orders with timestamps for timing metrics
            delivered_rows = base_q.filter(Order.status == 'delivered', Order.shipped_at.isnot(None), Order.delivered_at.isnot(None)).order_by(Order.delivered_at.desc()).all()
            on_time = sum(1 for order in delivered_rows if (order.delivered_at - order.shipped_at).days <= 3)
            on_time_rate = (on_time / delivered_count * 100.0) if delivered_count else 0.0
            avg_delivery_days = (sum((order.delivered_at - order.shipped_at).total_seconds() for order in delivered_rows) / 86400.0 / delivered_count) if delivered_count else 0.0
        except Exception:
            # Fallback: load and compute in Python if DB operations fail for some reason
            rows = base_q.order_by(Order.created_at.desc()).all()
            in_transit = sum(1 for order in rows if order.status == 'shipped')
            delivered_rows = [o for o in rows if o.status == 'delivered']
            delivered_count = len(delivered_rows)
            failed = sum(1 for order in rows if order.status == 'cancelled')
            on_time = sum(1 for order in delivered_rows if order.shipped_at and order.delivered_at and (order.delivered_at - order.shipped_at).days <= 3)
            on_time_rate = (on_time / delivered_count * 100.0) if delivered_count else 0.0
            avg_delivery_days = (sum((order.delivered_at - order.shipped_at).total_seconds() for order in delivered_rows if order.shipped_at and order.delivered_at) / 86400.0 / delivered_count) if delivered_count else 0.0

        stats = {
            'in_transit': in_transit,
            'on_time_rate': on_time_rate,
            'failed_attempts': failed,
            'avg_delivery_days': avg_delivery_days,
        }
        
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        pagination = base_q.filter(Order.status.in_(['shipped', 'delivered', 'cancelled'])).order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        recent_shipments = pagination.items if pagination else []

        return render_template('seller/delivery_services.html', stats=stats, recent_shipments=recent_shipments, pagination=pagination)

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

            target_category = request.form.get('target_category', '').strip() or None
            new_customer_only = request.form.get('new_customer_only') == 'true'
            min_item_count = int(request.form.get('min_item_count', 1))

            voucher_ref = f"VCH-S{current_user.id}-{datetime.utcnow().strftime('%y%m%d%H%M%S')}"
            try:
                voucher_payload = dict(
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
                )
                if hasattr(Voucher, 'target_category'):
                    voucher_payload['target_category'] = target_category
                if hasattr(Voucher, 'new_customer_only'):
                    voucher_payload['new_customer_only'] = new_customer_only
                if hasattr(Voucher, 'min_item_count'):
                    voucher_payload['min_item_count'] = min_item_count

                db.session.add(Voucher(**voucher_payload))
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
        # Use the standardized pagination helper and compute stats from the full result set
        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)

        base_q = db.session.query(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).filter(Product.seller_id == current_user.id).distinct()

        # Compute balances from full datasets (not just the page) so KPIs remain accurate
        delivered_orders = base_q.filter(Order.status == 'delivered').all()
        available_balance = sum(float(o.total or 0) for o in delivered_orders)
        pending_clearance = sum(float(o.total or 0) for o in base_q.filter(Order.status.in_(['paid', 'packed', 'shipped'])).all())

        today = datetime.utcnow().date()
        days_to_friday = (4 - today.weekday()) % 7
        next_transfer = today + timedelta(days=days_to_friday)

        stats = {
            'available_balance': available_balance,
            'pending_clearance': pending_clearance,
            'next_transfer': next_transfer,
            'payout_count': len(delivered_orders),
        }

        # History query (delivered/refunded)
        history_q = base_q.filter(Order.status.in_(['delivered', 'refunded']))

        # Export as CSV when requested
        if request.args.get('format') == 'csv':
            from flask import Response
            import io, csv
            rows = history_q.order_by(Order.delivered_at.desc() if hasattr(Order, 'delivered_at') else Order.created_at.desc()).all()
            si = io.StringIO()
            writer = csv.writer(si)
            writer.writerow(['order_ref', 'date', 'status', 'amount'])
            for o in rows:
                date = (o.delivered_at or o.created_at).strftime('%Y-%m-%d') if (o.delivered_at or o.created_at) else ''
                writer.writerow([o.order_ref, date, o.status, '%.2f' % float(o.total or 0)])
            output = si.getvalue()
            return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=payouts_{current_user.id}.csv'})

        # Paginate history for rendering
        pagination = history_q.order_by(Order.delivered_at.desc() if hasattr(Order, 'delivered_at') else Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        history = pagination.items

        # Page subtotal for the displayed rows
        page_total = sum(float(o.total or 0) for o in history)

        return render_template('seller/payouts.html', stats=stats, history=history, pagination=pagination, page_total=page_total)

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
                # handle avatar removal/upload for seller
                try:
                    if request.form.get('remove_profile_image') == '1':
                        try:
                            _remove_avatar_files('seller', current_user.id)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    upload = request.files.get('profile_image') if hasattr(request, 'files') else None
                    if upload and getattr(upload, 'filename', None):
                        ok, err = _save_avatar(upload, 'seller', current_user.id)
                        if not ok:
                            profile_errors['profile_image'] = err or 'Could not save uploaded image.'
                            return render_template('seller/profile.html', seller=current_user, errors=profile_errors, form=profile_data)
                except Exception:
                    pass

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

            if not is_seller_security_otp_fresh():
                challenge, otp_error = start_otp_flow(
                    user=current_user,
                    purpose='seller_security',
                    next_url=url_for('seller_security'),
                    mode='profile',
                    meta={'flow': 'seller_security_password_change'},
                )
                if not challenge:
                    errors = {'general': otp_error or 'Could not send security verification code.'}
                    return render_template('seller/security.html', errors=errors, form=form_data)
                session['otp_message'] = 'Check your email to confirm this seller security change.'
                return redirect(url_for('auth_otp_verify'))

            try:
                current_user.set_password(form_data['new_password'])
                db.session.commit()
                try:
                    try:
                        from .models.audit import AuditLog
                    except Exception:
                        from models.audit import AuditLog
                    try:
                        db.session.add(AuditLog(
                            actor_id=current_user.id,
                            actor_name=getattr(current_user, 'full_name', None) or current_user.email,
                            role=current_user.role,
                            action='password_changed',
                            module='security',
                            target_ref=current_user.email,
                            meta={'context': 'seller_security'},
                            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                        ))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                except Exception:
                    try:
                        app.logger.exception('Failed to record seller password change audit')
                    except Exception:
                        pass
                clear_seller_security_session()
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
            from .models.product import Product
            from .models.return_request import ReturnRequest
            from .models.audit import AuditLog
            from .models.otp_challenge import OtpChallenge
        except Exception:
            from models.product import Product
            from models.return_request import ReturnRequest
            from models.audit import AuditLog
            from models.otp_challenge import OtpChallenge

        now = datetime.utcnow()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_week = start_today - timedelta(days=6)

        # Non-transactional stats only: counts and alerts for escalations
        active_sellers = User.query.filter(User.role == 'seller', User.is_active.is_(True)).count()
        pending_sellers = User.query.filter(User.role == 'seller', User.seller_verification_status == 'pending').count()

        try:
            from .models.inquiry_ticket import InquiryTicket
        except Exception:
            from models.inquiry_ticket import InquiryTicket
        open_tickets = InquiryTicket.query.filter(InquiryTicket.status.in_(['open', 'in_progress'])).count()

        open_returns = ReturnRequest.query.filter(ReturnRequest.status.in_(['pending', 'accepted', 'refund_requested'])).count()

        system_errors = AuditLog.query.filter(AuditLog.created_at >= start_today, AuditLog.action.ilike('%fail%')).count()

        # OTP metrics (operational telemetry) kept for escalations awareness
        otp_rows = OtpChallenge.query.filter(OtpChallenge.created_at >= start_today).all()
        otp_sent_today = len(otp_rows)
        otp_verified_today = sum(1 for row in otp_rows if row.verified_at)
        otp_failed_today = sum(1 for row in otp_rows if row.failure_reason and row.failure_reason not in ('superseded',))
        otp_resend_today = sum(1 for row in otp_rows if row.failure_reason == 'superseded')
        otp_expired_today = sum(1 for row in otp_rows if row.consumed_at is None and row.expires_at and row.expires_at < now)
        otp_success_rate = round((otp_verified_today / otp_sent_today) * 100, 1) if otp_sent_today else 0.0

        # Top purposes
        purpose_counts = {}
        for row in otp_rows:
            purpose_counts[row.purpose] = purpose_counts.get(row.purpose, 0) + 1
        otp_top_purposes = [
            {'purpose': purpose, 'count': count}
            for purpose, count in sorted(purpose_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        recent_security = AuditLog.query.filter(
            AuditLog.created_at >= start_week,
            (AuditLog.module.ilike('%security%')) | (AuditLog.action.ilike('%login%')) | (AuditLog.action.ilike('%lock%'))
        ).order_by(AuditLog.created_at.desc()).limit(5).all()

        alerts = []
        if pending_sellers > 0:
            alerts.append({'title': 'Pending Seller Verification', 'message': f'{pending_sellers} seller account(s) waiting for review.', 'time': 'now'})
        if open_returns > 0:
            alerts.append({'title': 'Open Return/Refund Cases', 'message': f'{open_returns} return case(s) need admin visibility.', 'time': 'today'})
        if otp_sent_today > 0 and otp_success_rate < 70:
            alerts.append({'title': 'OTP Drop-off Elevated', 'message': f'OTP success rate is {otp_success_rate:.1f}% today. Review resend friction and verification copy.', 'time': 'today'})
        otp_lockouts_today = AuditLog.query.filter(
            AuditLog.module == 'otp',
            AuditLog.action.in_(['otp_locked', 'otp_rate_limited']),
            AuditLog.created_at >= start_today,
        ).count()
        if otp_lockouts_today > 0:
            alerts.append({'title': 'OTP Lockouts Detected', 'message': f'{otp_lockouts_today} OTP lockout/rate-limit event(s) today. Investigate potential abuse or delivery issues.', 'time': 'today'})
        for row in recent_security:
            alerts.append({
                'title': (row.action or 'Security Event').replace('_', ' ').title(),
                'message': row.target_ref or row.module or 'Security-related activity detected.',
                'time': row.created_at.strftime('%b %d, %H:%M') if row.created_at else '-',
            })

        if not alerts:
            alerts.append({'title': 'No Critical Alerts', 'message': 'All monitored systems are currently stable.', 'time': '-'})

        # Non-transactional counts
        total_customers = User.query.filter(User.role == 'customer').count()
        total_products = Product.query.count()
        low_stock_count = Product.query.filter(Product.stock <= Product.low_stock_threshold).count()

        stats = {
            'active_sellers': active_sellers,
            'system_errors': system_errors,
            'open_tickets': open_tickets,
            'pending_returns': open_returns,
            'otp_sent_today': otp_sent_today,
            'otp_verified_today': otp_verified_today,
            'otp_failed_today': otp_failed_today,
            'otp_resend_today': otp_resend_today,
            'otp_expired_today': otp_expired_today,
            'otp_success_rate': otp_success_rate,
            'otp_top_purposes': otp_top_purposes,
            'total_customers': total_customers,
            'total_products': total_products,
            'low_stock_count': low_stock_count,
        }

        return render_template('admin/dashboard.html', stats=stats, alerts=alerts, otp_top_purposes=otp_top_purposes)

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
                flash('Seller entity not found.', 'error')
            else:
                try:
                    if action == 'approve':
                        seller.seller_verification_status = 'approved'
                        seller.is_active = True
                        
                        # Generate SLR code if missing
                        if not seller.seller_code:
                            import random, string
                            while True:
                                new_code = 'SLR-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                                if not User.query.filter_by(seller_code=new_code).first():
                                    seller.seller_code = new_code
                                    break
                                    
                        db.session.commit()
                        write_audit('approve_seller', seller.email, {'seller_id': seller.id, 'code': seller.seller_code})
                        flash(f'Seller {seller.email} successfully verified and activated as {seller.seller_code}.', 'success')
                    elif action == 'reject':
                        seller.seller_verification_status = 'rejected'
                        seller.is_active = False
                        db.session.commit()
                        write_audit('reject_seller', seller.email, {'seller_id': seller.id})
                        flash(f'Application for {seller.email} has been rejected.', 'warning')
                    elif action == 'suspend':
                        seller.seller_verification_status = 'suspended'
                        seller.is_active = False
                        db.session.commit()
                        write_audit('suspend_seller', seller.email, {'seller_id': seller.id})
                        flash(f'Seller {seller.email} has been suspended.', 'warning')
                    elif action == 'delete':
                        ref = seller.email
                        db.session.delete(seller)
                        db.session.commit()
                        write_audit('delete_seller', ref, {'seller_id': seller_id})
                        flash(f'Seller {ref} has been removed.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Governance Error: Could not update seller state. {str(e)}', 'error')
            return redirect(url_for('admin_sellers', q=request.args.get('q', ''), status=request.args.get('status', 'all')))

        try:
            from .models.product import Product
            from .models.order import Order
        except Exception:
            from models.product import Product
            from models.order import Order

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip().lower()

        query = User.query.filter(User.role == 'seller')
        if q and len(q) >= 2:
            like_q = f"%{q}%"
            query = query.filter((User.email.ilike(like_q)) | (User.business_name.ilike(like_q)) | (User.full_name.ilike(like_q)))
        if status_filter in ('pending', 'approved', 'rejected'):
            query = query.filter(User.seller_verification_status == status_filter)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active.is_(False))

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        paginated_sellers = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        product_count_by_seller = {}
        for row in Product.query.filter(Product.seller_id.in_([s.id for s in paginated_sellers.items])).all():
            product_count_by_seller[row.seller_id] = int(product_count_by_seller.get(row.seller_id, 0)) + 1

        rows = []
        for seller in paginated_sellers.items:
            rows.append({
                'seller': seller,
                'product_count': int(product_count_by_seller.get(seller.id, 0)),
                'status': 'suspended' if (not seller.is_active and seller.seller_verification_status == 'approved') else (seller.seller_verification_status or 'pending').lower(),
            })

        total_gmv = sum(float(o.total or 0) for o in Order.query.filter(Order.status.in_(['paid', 'packed', 'shipped', 'delivered'])).all())
        stats = {
            'verified': User.query.filter(User.role == 'seller', User.seller_verification_status == 'approved').count(),
            'pending': User.query.filter(User.role == 'seller', User.seller_verification_status == 'pending').count(),
            'suspended': User.query.filter(User.role == 'seller', User.is_active.is_(False), User.seller_verification_status == 'approved').count(),
            'gmv_share': total_gmv,
        }

        return render_template('admin/sellers.html', sellers=rows, pagination=paginated_sellers, stats=stats, filters={'q': q, 'status': status_filter})

    @app.route('/admin/permits/<path:filename>')
    def admin_view_permit(filename):
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return abort(403)
        
        from flask import send_from_directory
        # ── Path traversal prevention ─────────────────────────────────
        safe_dir = os.path.abspath(os.path.join(app.instance_path, 'uploads', 'permits'))
        abs_path = os.path.abspath(os.path.join(safe_dir, filename))
        if not abs_path.startswith(safe_dir):
            return abort(403)
        return send_from_directory(safe_dir, filename)

    @app.route('/uploads/products/<path:filename>')
    def uploads_products_view(filename):
        # Public route to serve seller-uploaded product images safely from instance uploads
        from flask import send_from_directory
        safe_dir = os.path.abspath(os.path.join(app.instance_path, 'uploads', 'products'))
        abs_path = os.path.abspath(os.path.join(safe_dir, filename))
        if not abs_path.startswith(safe_dir):
            return abort(403)
        return send_from_directory(safe_dir, filename)

    @app.route('/admin/sellers/<seller_id>', methods=['GET', 'POST'])
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

        def run_admin_action(action_payload):
            action = (action_payload.get('action') or '').strip()
            try:
                if action == 'approve':
                    seller.seller_verification_status = 'approved'
                    seller.is_active = True

                    if not seller.seller_code:
                        import random, string
                        while True:
                            new_code = 'SLR-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                            if not User.query.filter_by(seller_code=new_code).first():
                                seller.seller_code = new_code
                                break

                    db.session.commit()
                    flash(f'Approved {seller.email} (Code: {seller.seller_code}).', 'success')
                elif action == 'reject':
                    seller.seller_verification_status = 'rejected'
                    seller.is_active = False
                    db.session.commit()
                    flash(f'Rejected {seller.email}.', 'warning')
                elif action == 'delete_product':
                    try:
                        product_id = int(action_payload.get('product_id') or 0)
                    except Exception:
                        product_id = 0
                    product = Product.query.get(product_id)
                    if product and product.seller_id == seller.id:
                        ref = product.product_ref
                        db.session.delete(product)
                        db.session.commit()
                        flash(f'Listing {ref} has been removed from the platform.', 'success')
                    else:
                        flash('Product not found or unauthorized.', 'error')
                else:
                    flash('No privileged action was selected.', 'error')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating seller: {str(e)}', 'error')

        if request.method == 'GET' and session.get('pending_admin_action') and is_admin_action_otp_fresh():
            pending_action = session.get('pending_admin_action') or {}
            if str(pending_action.get('seller_id') or '') == str(seller.id):
                run_admin_action(pending_action)
                clear_admin_action_session()
                return redirect(url_for('admin_seller_detail', seller_id=seller.id))

        if request.method == 'POST':
            action_payload = request.form.to_dict(flat=True)
            action_payload['seller_id'] = str(seller.id)
            if not is_admin_action_otp_fresh():
                session['pending_admin_action'] = action_payload
                challenge, otp_error = start_otp_flow(
                    user=current_user,
                    purpose='admin_action',
                    next_url=url_for('admin_seller_detail', seller_id=seller.id),
                    mode='admin',
                    meta={'flow': 'admin_seller_detail', 'seller_id': str(seller.id), 'action': action_payload.get('action')},
                )
                if not challenge:
                    clear_admin_action_session()
                    flash(otp_error or 'Could not send admin verification code.', 'error')
                    return redirect(url_for('admin_seller_detail', seller_id=seller.id))
                session['otp_message'] = 'Check your email to confirm this admin action.'
                return redirect(url_for('auth_otp_verify'))

            run_admin_action(action_payload)
            clear_admin_action_session()
            return redirect(url_for('admin_seller_detail', seller_id=seller.id))

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        all_products_query = Product.query.filter_by(seller_id=seller.id)
        all_products = all_products_query.all()
        
        paginated_products = all_products_query.order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        
        product_ids = [p.id for p in all_products]
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
            (AuditLog.target_ref == seller.email) | (AuditLog.target_ref == (seller.seller_code or 'UNKNOWN'))
        ).order_by(AuditLog.created_at.desc()).limit(8).all()

        metrics = {
            'products': len(all_products),
            'orders': len(orders),
            'returns': int(returns_count),
            'payout_total': payout_total,
        }

        return render_template(
            'admin/seller_detail.html',
            seller=seller,
            metrics=metrics,
            products=paginated_products,
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

        q = sanitize_search_query(request.args.get('q') or '')
        action_filter = (request.args.get('action') or 'all').strip().lower()
        module_filter = (request.args.get('module') or 'all').strip().lower()

        query = AuditLog.query
        if q and len(q) >= 2:
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

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = query
        pagination = base_q.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        logs = pagination.items

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = {
            'actions_today': AuditLog.query.filter(AuditLog.created_at >= today_start).count(),
            'security_events': AuditLog.query.filter(AuditLog.created_at >= today_start, AuditLog.module.ilike('%security%')).count(),
            'admin_changes': AuditLog.query.filter(AuditLog.created_at >= today_start, AuditLog.role == 'admin').count(),
            'reveal_actions': AuditLog.query.filter(AuditLog.created_at >= today_start, AuditLog.action.ilike('%reveal%')).count(),
        }

        return render_template('admin/audit.html', logs=logs, pagination=pagination, stats=stats, filters={'q': q, 'action': action_filter, 'module': module_filter})

    @app.route('/admin/trusted-devices', methods=['GET', 'POST'])
    def admin_trusted_devices():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        from eacis.services.trusted_device_service import revoke_admin_by_id
        from eacis.models.audit import AuditLog
        from eacis.models.trusted_device import TrustedDevice
        from eacis.models.user import User

        q = sanitize_search_query(request.args.get('q') or '')

        if request.method == 'POST':
            revoke_id = request.form.get('revoke_id')
            if revoke_id:
                ok = revoke_admin_by_id(revoke_id)
                try:
                    db.session.add(AuditLog(
                        actor_id=current_user.id,
                        actor_name=getattr(current_user, 'full_name', None) or current_user.email,
                        role='admin',
                        action='trusted_device_revoked',
                        module='security',
                        target_ref=str(revoke_id),
                        meta={'q': q},
                        ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                    ))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                if ok:
                    flash('Trusted device revoked.', 'success')
                else:
                    flash('Trusted device not found.', 'error')
                return redirect(url_for('admin_trusted_devices', q=q))

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        base_q = TrustedDevice.query.join(User, User.id == TrustedDevice.user_id)
        if q and len(q) >= 2:
            like_q = f"%{q}%"
            base_q = base_q.filter(User.email.ilike(like_q))

        pagination = base_q.order_by(TrustedDevice.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        td_items = pagination.items
        user_ids = [int(td.user_id) for td in td_items]
        users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u for u in users}
        devices = []
        for td in td_items:
            devices.append({'device': td, 'user_email': getattr(user_map.get(int(td.user_id)), 'email', None), 'user_id': td.user_id})

        return render_template('admin/trusted_devices.html', devices=devices, pagination=pagination, q=q)

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
                    # Admin can only manage visibility, NOT price or stock
                    status_val = request.form.get('is_active')
                    if status_val is not None:
                        product.is_active = status_val == '1'
                    db.session.commit()
                    flash(f'Status updated for {product.product_ref}.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Update failed: {str(e)}', 'error')
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

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip()

        query = Product.query
        if q and len(q) >= 2:
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

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        stats = {
            'total': Product.query.count(),
            'active': Product.query.filter(Product.is_active.is_(True)).count(),
            'low_stock': Product.query.filter(Product.stock <= Product.low_stock_threshold).count(),
        }

        return render_template(
            'admin/products.html',
            products=pagination.items,
            pagination=pagination,
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

        q = sanitize_search_query(request.args.get('q') or '')
        status_filter = (request.args.get('status') or 'all').strip()
        query = Product.query
        if q and len(q) >= 2:
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
                            old_active = user.is_active
                            # Role editing is now restricted for security
                            user.is_active = is_active
                            user.full_name = full_name
                            db.session.commit()
                            write_audit(
                                'update_user',
                                user.email,
                                {
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

        q = sanitize_search_query(request.args.get('q') or '')
        role_filter = (request.args.get('role') or 'all').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = User.query
        if q and len(q) >= 2:
            like_q = f"%{q}%"
            query = query.filter((User.email.ilike(like_q)) | (User.full_name.ilike(like_q)))
        if role_filter in ('customer', 'seller', 'admin'):
            query = query.filter(User.role == role_filter)
        if status_filter == 'active':
            query = query.filter(User.is_active.is_(True))
        elif status_filter == 'inactive':
            query = query.filter(User.is_active.is_(False))

        try:
            from .utils.pagination import get_page_args
        except Exception:
            from utils.pagination import get_page_args

        page, per_page = get_page_args(default_per_page=10)
        pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        stats = {
            'total': User.query.count(),
            'active': User.query.filter(User.is_active.is_(True)).count(),
            'customers': User.query.filter(User.role == 'customer').count(),
            'sellers': User.query.filter(User.role == 'seller').count(),
            'admins': User.query.filter(User.role == 'admin').count(),
        }
        return render_template(
            'admin/customers.html',
            users=pagination.items,
            pagination=pagination,
            stats=stats,
            filters={'q': q, 'role': role_filter, 'status': status_filter},
        )

    @app.route('/admin/customers/export')
    def admin_customers_export():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        q = sanitize_search_query(request.args.get('q') or '')
        role_filter = (request.args.get('role') or 'all').strip()
        status_filter = (request.args.get('status') or 'all').strip()

        query = User.query
        if q and len(q) >= 2:
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

    @app.route('/admin/profile', methods=['GET', 'POST'])
    def admin_profile():
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

        user = current_user
        if request.method == 'POST':
            full_name = (request.form.get('full_name') or '').strip()
            current_pwd = request.form.get('current_password') or ''
            new_pwd = request.form.get('new_password') or ''
            confirm_pwd = request.form.get('confirm_password') or ''
            errors = []
            changed = False
            if full_name and full_name != (user.full_name or ''):
                user.full_name = full_name
                changed = True

            if new_pwd:
                if not user.check_password(current_pwd):
                    errors.append('Current password is incorrect.')
                elif len(new_pwd) < 8:
                    errors.append('New password must be at least 8 characters.')
                elif new_pwd != confirm_pwd:
                    errors.append('New passwords do not match.')
                else:
                    user.set_password(new_pwd)
                    changed = True

            if errors:
                for e in errors:
                    flash(e, 'error')
            else:
                if changed:
                    try:
                        db.session.commit()
                        if AuditLog is not None:
                            try:
                                db.session.add(AuditLog(
                                    actor_id=user.id,
                                    actor_name=getattr(user, 'full_name', None) or user.email,
                                    role='admin',
                                    action='update_profile',
                                    module='admin',
                                    target_ref=user.email,
                                    meta={},
                                    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                                ))
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                        flash('Profile updated.', 'success')
                    except Exception:
                        db.session.rollback()
                        flash('Could not update profile. Try again later.', 'error')
                else:
                    flash('No changes detected.', 'info')

                return redirect(url_for('admin_profile'))

        return render_template('admin/profile.html', user=user)

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
