from flask import Flask, render_template
from flask import redirect, url_for, request, jsonify
from flask import flash, session
import time
import csv
import io
from datetime import datetime, timedelta
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
    from .extensions import db, csrf, login_manager
except Exception:
    try:
        from extensions import db, csrf, login_manager
    except Exception:
        from eacis.extensions import db, csrf, login_manager

 
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

    @app.route('/api/cart/summary')
    def api_cart_summary():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return jsonify({'items': [], 'count': 0, 'subtotal': 0.0})

        try:
            from .models.cart import Cart
            from .models.product import Product
        except Exception:
            from models.cart import Cart
            from models.product import Product

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
        # allow static, api, auth and landing
        allowed_prefixes = ('/static/', '/api/', '/auth', '/', '/landing', '/shop', '/product', '/about', '/contact', '/terms', '/privacy')
        if any(path.startswith(p) for p in allowed_prefixes):
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

    @app.route('/')
    def index():
        return render_template('landing.html')

    @app.route('/landing')
    def landing():
        return render_template('landing.html')

    @app.route('/auth/login')
    def auth_login():
        # GET renders the form; POST handles submission
        if request.method == 'POST':
            try:
                email = request.form.get('email','').strip().lower()
                password = request.form.get('password','')
                remember = bool(request.form.get('remember'))
                locked_until = session.get('locked_until', 0)
                if time.time() < locked_until:
                    remaining = int(locked_until - time.time())
                    error = f"Account temporarily locked. Try again in {remaining} seconds."
                    return render_template('auth/login.html', error=error)
                user = User.query.filter_by(email=email).first()
                if not user or not user.check_password(password):
                    session['failed_attempts'] = session.get('failed_attempts',0) + 1
                    if session['failed_attempts'] >= 5:
                        session['locked_until'] = time.time() + 600
                        session['failed_attempts'] = 0
                        error = 'Account temporarily locked. Try again in 600 seconds.'
                    else:
                        error = 'Incorrect email or password. Try again.'
                    return render_template('auth/login.html', error=error)
                
                # Check portal authorization
                portal = request.form.get('portal', 'customer')
                if portal == 'customer' and user.role not in ['customer', 'admin']:
                    error = 'This portal is for customers. Please select Seller to log in.'
                    return render_template('auth/login.html', error=error)
                if portal == 'seller' and user.role not in ['seller', 'admin']:
                    error = 'This portal is for sellers and admins. Please select Customer to log in.'
                    return render_template('auth/login.html', error=error)

                # success
                from flask_login import login_user
                login_user(user, remember=remember)
                session.pop('failed_attempts', None)
                session.pop('locked_until', None)
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
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                try:
                    with open('tools/login_error.log','w', encoding='utf-8') as f:
                        f.write(tb)
                        try:
                            f.write('\n--- SQLAlchemy engines state:\n')
                            engines = getattr(db, 'engines', None)
                            f.write(repr(engines) + '\n')
                            if isinstance(engines, dict):
                                for k in engines.keys():
                                    f.write(f' engine key: {k!r} type={type(k)} id={id(k) if k is not None else None}\n')
                        except Exception as e2:
                            f.write('Could not inspect db.engines: ' + str(e2) + '\n')
                except Exception:
                    pass
                raise
        return render_template('auth/login.html')
    # allow POST on the same endpoint
    app.add_url_rule('/auth/login', endpoint='auth_login', view_func=auth_login, methods=['GET','POST'])

    @app.route('/auth/register', methods=['GET','POST'])
    def auth_register():
        if request.method == 'POST':
            import re
            errors = {}
            full_name = request.form.get('full_name', '').strip()
            email     = request.form.get('email', '').strip().lower()
            phone     = request.form.get('phone', '').strip()
            password  = request.form.get('password', '')
            confirm   = request.form.get('confirm_password', '')
            role      = request.form.get('role', 'customer')
            agree     = request.form.get('agree')

            # Full name
            if len(full_name) < 2:
                errors['full_name'] = 'Please enter your full name (at least 2 characters).'
            elif not re.match(r"^[a-zA-Z\s'-]+$", full_name):
                errors['full_name'] = 'Name may only contain letters, spaces, hyphens, and apostrophes.'

            # Email
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                errors['email'] = 'Please enter a valid email address.'
            elif User.query.filter_by(email=email).first():
                errors['email'] = 'An account with this email already exists.'

            # Phone (optional but if provided must be valid PH format)
            if phone and not re.match(r'^(\+63|0)9\d{9}$', phone):
                errors['phone'] = 'Enter a valid Philippine mobile number (e.g. 09171234567).'

            # Password strength
            if len(password) < 8:
                errors['password'] = 'Password must be at least 8 characters.'
            elif not re.search(r'[A-Z]', password):
                errors['password'] = 'Password must contain at least one uppercase letter.'
            elif not re.search(r'\d', password):
                errors['password'] = 'Password must contain at least one number.'

            # Confirm password
            if password != confirm:
                errors['confirm_password'] = 'Passwords do not match.'

            # Role
            if role not in ('customer', 'seller'):
                errors['role'] = 'Please select a valid portal.'

            # Terms
            if not agree:
                errors['agree'] = 'You must agree to the Terms & Conditions to continue.'

            if errors:
                return render_template('auth/register.html', errors=errors,
                    form=dict(full_name=full_name, email=email, phone=phone, role=role))

            try:
                new_user = User(
                    email=email,
                    role=role,
                    full_name=full_name,
                    phone=phone or None
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                from flask_login import login_user
                login_user(new_user)
                dest = url_for('shop') if role == 'customer' else url_for('seller_dashboard')
                return redirect(dest)
            except Exception:
                db.session.rollback()
                errors['general'] = 'Something went wrong. Please try again.'
                return render_template('auth/register.html', errors=errors,
                    form=dict(full_name=full_name, email=email, phone=phone, role=role))

        return render_template('auth/register.html', errors={}, form={})

    @app.route('/auth/logout')
    def auth_logout():
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('index'))

    # Customer Portal Routes (Aliased for /customer/* paths)
    @app.route('/customer/home')
    def customer_home():
        return render_template('customer/home.html', view_mode='discovery')

    @app.route('/shop')
    def shop():
        return render_template('customer/home.html', view_mode='catalog')

    @app.route('/customer/product/<ref>')
    @app.route('/products/<ref>')
    def product_detail(ref):
        return render_template('customer/product_detail.html', ref=ref)

    @app.route('/customer/cart', methods=['GET', 'POST'])
    @app.route('/cart', methods=['GET', 'POST'])
    def cart():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from .models.cart import Cart
            from .models.product import Product
        except Exception:
            from models.cart import Cart
            from models.product import Product

        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if cart is None:
            cart = Cart(user_id=current_user.id, items=[])
            db.session.add(cart)
            db.session.commit()

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            items = list(cart.items or [])
            if action == 'add':
                product_id = request.form.get('product_id', type=int)
                product_ref = (request.form.get('product_ref') or '').strip()
                qty = max(request.form.get('qty', type=int) or 1, 1)
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
                qty = max(request.form.get('qty', type=int) or 1, 1)
                updated = False
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
                db.session.commit()
                flash('Cart cleared.', 'success')
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

        return render_template('customer/cart.html', cart_lines=cart_lines, subtotal=subtotal, has_items=bool(cart_lines))

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
        except Exception:
            from models.cart import Cart
            from models.order import Order, OrderItem
            from models.product import Product
            from models.voucher import Voucher
            from models.loyalty import LoyaltyTransaction

        cart = Cart.query.filter_by(user_id=current_user.id).first()
        cart_items = []
        subtotal = 0.0
        if cart and cart.items:
            for entry in cart.items:
                product = Product.query.get(entry.get('product_id'))
                if not product:
                    continue
                quantity = max(int(entry.get('qty') or 1), 1)
                line_total = float(product.price or 0) * quantity
                subtotal += line_total
                cart_items.append({'product': product, 'qty': quantity, 'line_total': line_total})

        voucher_code = ''
        voucher_discount = 0.0
        voucher = None
        loyalty_requested = 0
        loyalty_applied = 0
        available_points = int(getattr(current_user, 'loyalty_points', 0) or 0)

        if request.method == 'POST':
            voucher_code = (request.form.get('voucher_code') or '').strip()
            loyalty_requested = max(request.form.get('loyalty_points', type=int) or 0, 0)
        else:
            voucher_code = (request.args.get('voucher_code') or '').strip()
            loyalty_requested = max(request.args.get('loyalty_points', type=int) or 0, 0)

        if voucher_code:
            voucher = Voucher.query.filter(Voucher.code.ilike(voucher_code)).first()
            if not voucher:
                if request.method == 'POST':
                    flash('Voucher code not found.', 'error')
                voucher_code = ''
            else:
                if not voucher.is_valid():
                    if request.method == 'POST':
                        flash('Voucher is not active or already expired.', 'error')
                    voucher = None
                elif float(subtotal) < float(voucher.min_order_amount or 0):
                    if request.method == 'POST':
                        flash(f'Voucher requires minimum order of PHP {float(voucher.min_order_amount or 0):.2f}.', 'error')
                    voucher = None
                elif voucher.max_uses is not None and int(voucher.uses_count or 0) >= int(voucher.max_uses):
                    if request.method == 'POST':
                        flash('Voucher has reached maximum redemptions.', 'error')
                    voucher = None
                else:
                    used_count = Order.query.filter_by(customer_id=current_user.id, voucher_id=voucher.id).count()
                    if voucher.per_user_limit is not None and used_count >= int(voucher.per_user_limit):
                        if request.method == 'POST':
                            flash('You have reached your usage limit for this voucher.', 'error')
                        voucher = None

            if voucher:
                if (voucher.discount_type or '').strip() == 'percent':
                    voucher_discount = float(subtotal) * (float(voucher.discount_value or 0) / 100.0)
                else:
                    voucher_discount = float(voucher.discount_value or 0)
                voucher_discount = max(min(voucher_discount, float(subtotal)), 0.0)

        max_loyalty_value = max(float(subtotal) - voucher_discount, 0.0)
        loyalty_applied = min(loyalty_requested, available_points, int(max_loyalty_value))
        discount_total = voucher_discount + float(loyalty_applied)
        order_total = max(float(subtotal) - discount_total, 0.0)
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
                    subtotal=float(subtotal),
                    voucher_code=voucher_code,
                    voucher_discount=float(voucher_discount),
                    loyalty_requested=int(loyalty_requested),
                    loyalty_applied=int(loyalty_applied),
                    available_points=int(available_points),
                    order_total=float(order_total),
                    earned_points=int(earned_points),
                )

            payment_method = (request.form.get('payment') or 'full_pay').strip()
            if payment_method == 'credit' or payment_method == 'wallet' or payment_method == 'cod':
                payment_method = 'full_pay'
            elif payment_method == 'installment':
                payment_method = 'installment'
            else:
                payment_method = 'full_pay'

            address = {
                'line1': request.form.get('address_line1') or request.form.get('address') or '',
                'city': request.form.get('city') or '',
                'province': request.form.get('province') or '',
                'country': 'Philippines',
                'phone': request.form.get('phone') or current_user.phone or '',
            }

            try:
                order_ref = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                order = Order(
                    order_ref=order_ref,
                    customer_id=current_user.id,
                    status='paid' if payment_method == 'full_pay' else 'pending',
                    subtotal=subtotal,
                    discount=discount_total,
                    shipping_fee=0,
                    tax=0,
                    total=order_total,
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
                    db.session.add(OrderItem(
                        order_id=order.id,
                        product_id=line['product'].id,
                        quantity=line['qty'],
                        unit_price=line['product'].price,
                        subtotal=line['line_total'],
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

                cart.items = []
                db.session.commit()
                return redirect(url_for('checkout_success', order_ref=order_ref))
            except Exception:
                db.session.rollback()
                flash('Could not place your order. Please try again.', 'error')

        return render_template(
            'customer/checkout.html',
            cart_items=cart_items,
            subtotal=float(subtotal),
            voucher_code=voucher_code,
            voucher_discount=float(voucher_discount),
            loyalty_requested=int(loyalty_requested),
            loyalty_applied=int(loyalty_applied),
            available_points=int(available_points),
            order_total=float(order_total),
            earned_points=int(earned_points),
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

        if request.method == 'POST':
            order_ref = (request.form.get('order_ref') or '').strip()
            reason = (request.form.get('reason') or '').strip()
            description = (request.form.get('description') or '').strip()
            order = Order.query.filter_by(order_ref=order_ref, customer_id=current_user.id).first()
            if not order:
                flash('Please choose one of your own orders.', 'error')
            elif not reason or not description:
                flash('Reason and description are required.', 'error')
            else:
                try:
                    ts = datetime.utcnow().strftime('%y%m%d%H%M%S')
                    rrt_ref = f'RET-{current_user.id}-{ts}'
                    item = ReturnRequest(
                        rrt_ref=rrt_ref,
                        order_id=order.id,
                        customer_id=current_user.id,
                        reason=reason,
                        description=description,
                        status='pending',
                    )
                    db.session.add(item)
                    db.session.commit()
                    flash(f'Return request {rrt_ref} submitted.', 'success')
                    return redirect(url_for('customer_returns'))
                except Exception:
                    db.session.rollback()
                    flash('Could not submit return request.', 'error')

        orders = Order.query.filter(Order.customer_id == current_user.id).order_by(Order.created_at.desc()).all()
        returns = ReturnRequest.query.filter(ReturnRequest.customer_id == current_user.id).order_by(ReturnRequest.created_at.desc()).all()
        return render_template('customer/returns.html', orders=orders, returns=returns)

    @app.route('/customer/loyalty')
    def customer_loyalty():
        return render_template('customer/loyalty.html')

    @app.route('/customer/profile')
    def customer_profile():
        return render_template('customer/profile.html')

    @app.route('/customer/profile/edit')
    def customer_profile_edit():
        return render_template('customer/profile_edit.html')

    @app.route('/customer/wishlist')
    def customer_wishlist():
        # Using home template as placeholder for now
        return render_template('customer/home.html')

    @app.route('/about')
    def about(): return render_template('static_pages.html', title='About E-ACIS')

    @app.route('/contact')
    def contact(): return render_template('static_pages.html', title='Contact Us')

    @app.route('/terms')
    def terms(): return render_template('static_pages.html', title='Terms of Service')

    @app.route('/privacy')
    def privacy(): return render_template('static_pages.html', title='Privacy Policy')

    # Seller preview routes (static templates)
    @app.route('/seller/dashboard')
    def seller_dashboard():
        return render_template('seller/dashboard.html')

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
        return render_template('seller/product_form.html', ref=None, product=None)

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

        name = (request.form.get('name') or '').strip()
        category = (request.form.get('category') or '').strip()
        description = (request.form.get('description') or '').strip()
        price_raw = request.form.get('price')
        stock_raw = request.form.get('stock')
        warranty_raw = request.form.get('warranty_months')
        is_active = (request.form.get('is_active') or '1').strip() == '1'
        installment_enabled = bool(request.form.get('installment_enabled'))

        try:
            price = float(price_raw or 0)
        except Exception:
            price = -1
        try:
            stock = int(stock_raw or 0)
        except Exception:
            stock = -1
        try:
            warranty_months = int(warranty_raw or 0)
        except Exception:
            warranty_months = 0

        errors = []
        if not name or len(name) < 3:
            errors.append('Product name must be at least 3 characters.')
        if price < 0:
            errors.append('Price must be a valid non-negative number.')
        if stock < 0:
            errors.append('Stock must be a valid non-negative integer.')
        if not category:
            errors.append('Category is required.')

        if errors:
            flash(' '.join(errors), 'error')
            form_product = {
                'name': name,
                'category': category,
                'description': description,
                'price': price_raw,
                'stock': stock_raw,
                'warranty_months': warranty_raw,
                'is_active': is_active,
                'installment_enabled': installment_enabled,
            }
            return render_template('seller/product_form.html', ref=None, product=form_product)

        ts = datetime.utcnow().strftime('%y%m%d%H%M%S')
        product_ref = f"PRD-S{current_user.id}-{ts}"
        try:
            product = Product(
                product_ref=product_ref,
                seller_id=current_user.id,
                name=name,
                category=category,
                description=description,
                price=price,
                stock=stock,
                warranty_months=max(warranty_months, 0),
                installment_enabled=installment_enabled,
                is_active=is_active,
            )
            db.session.add(product)
            db.session.commit()
            flash(f'Product {product_ref} created successfully.', 'success')
            return redirect(url_for('seller_products'))
        except Exception:
            db.session.rollback()
            flash('Unable to create product right now.', 'error')
            form_product = {
                'name': name,
                'category': category,
                'description': description,
                'price': price_raw,
                'stock': stock_raw,
                'warranty_months': warranty_raw,
                'is_active': is_active,
                'installment_enabled': installment_enabled,
            }
            return render_template('seller/product_form.html', ref=None, product=form_product)

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
        return render_template('seller/product_form.html', ref=ref, product=product)

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

        name = (request.form.get('name') or '').strip()
        category = (request.form.get('category') or '').strip()
        description = (request.form.get('description') or '').strip()
        price_raw = request.form.get('price')
        stock_raw = request.form.get('stock')
        warranty_raw = request.form.get('warranty_months')
        is_active = (request.form.get('is_active') or '1').strip() == '1'
        installment_enabled = bool(request.form.get('installment_enabled'))

        try:
            price = float(price_raw or 0)
        except Exception:
            price = -1
        try:
            stock = int(stock_raw or 0)
        except Exception:
            stock = -1
        try:
            warranty_months = int(warranty_raw or 0)
        except Exception:
            warranty_months = 0

        errors = []
        if not name or len(name) < 3:
            errors.append('Product name must be at least 3 characters.')
        if not category:
            errors.append('Category is required.')
        if price < 0:
            errors.append('Price must be a valid non-negative number.')
        if stock < 0:
            errors.append('Stock must be a valid non-negative integer.')

        if errors:
            flash(' '.join(errors), 'error')
            return render_template('seller/product_form.html', ref=ref, product=product)

        try:
            product.name = name
            product.category = category
            product.description = description
            product.price = price
            product.stock = stock
            product.warranty_months = max(warranty_months, 0)
            product.is_active = is_active
            product.installment_enabled = installment_enabled
            db.session.commit()
            flash(f'Product {ref} updated.', 'success')
            return redirect(url_for('seller_product_detail', ref=ref))
        except Exception:
            db.session.rollback()
            flash('Unable to update product.', 'error')
            return render_template('seller/product_form.html', ref=ref, product=product)

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
        return render_template('seller/inventory.html')

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
        return render_template(
            'seller/orders.html',
            page_title='Customer Orders',
            page_subtitle='Manage checkout-confirmed orders and fulfillment progression.',
            export_label='Export Orders'
        )

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
        except Exception:
            from models.return_request import ReturnRequest
            from models.order import OrderItem
            from models.product import Product

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
        except Exception:
            from models.return_request import ReturnRequest
            from models.order import OrderItem
            from models.product import Product

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

        action = (request.form.get('action') or '').strip()
        notes = (request.form.get('seller_notes') or '').strip()
        if action == 'approve':
            return_request.status = 'accepted'
        elif action == 'deny':
            return_request.status = 'rejected'
        elif action == 'refund':
            return_request.status = 'refunded'
        else:
            flash('Invalid return action.', 'error')
            return redirect(url_for('seller_returns'))

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
    def seller_return_transactions():
        return render_template(
            'seller/returns.html',
            page_title='Return Transactions',
            page_subtitle='Review active RMA requests, disposition, and refund outcomes.'
        )

    @app.route('/seller/vouchers')
    def seller_vouchers():
        return render_template('seller/vouchers.html')

    @app.route('/seller/analytics')
    @app.route('/seller/sales-analytics')
    def seller_analytics():
        return render_template('seller/analytics.html')

    @app.route('/seller/financial-analytics')
    def seller_financial_analytics():
        return render_template('seller/financial_analytics.html')

    @app.route('/seller/installment-payments')
    def seller_installment_payments():
        return render_template('seller/installment_payments.html')

    @app.route('/seller/customer-inquiries')
    def seller_customer_inquiries():
        return render_template('seller/customer_inquiries.html')

    @app.route('/seller/customer-accounts')
    def seller_customer_accounts():
        return render_template('seller/customer_accounts.html')

    @app.route('/seller/crm-analytics')
    def seller_crm_analytics():
        return render_template('seller/crm_analytics.html')

    @app.route('/seller/inventory-analytics')
    def seller_inventory_analytics():
        return render_template('seller/inventory_analytics.html')

    @app.route('/seller/delivery-services')
    def seller_delivery_services():
        return render_template('seller/delivery_services.html')

    @app.route('/seller/vouchers/create')
    def seller_voucher_create():
        return render_template('seller/vouchers.html', create_mode=True)

    @app.route('/seller/payouts')
    def seller_payouts():
        return render_template('seller/payouts.html')

    @app.route('/seller/profile')
    def seller_profile():
        return render_template('seller/profile.html')

    @app.route('/seller/security')
    def seller_security():
        return render_template('seller/security.html')

    # Admin preview routes (static templates)
    @app.route('/admin/dashboard')
    def admin_dashboard():
        return render_template('admin/dashboard.html')

    @app.route('/admin/refunds')
    def admin_refunds():
        return render_template('admin/refunds.html')

    @app.route('/admin/refunds/<ref>')
    def admin_refund_detail(ref):
        return render_template('admin/refund_detail.html', ref=ref)

    @app.route('/admin/sellers')
    def admin_sellers():
        return render_template('admin/sellers.html')

    @app.route('/admin/sellers/<seller_id>')
    def admin_seller_detail(seller_id):
        return render_template('admin/seller_detail.html', seller_id=seller_id)

    @app.route('/admin/audit')
    def admin_audit():
        return render_template('admin/audit.html')

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
        return render_template('admin/settings.html')

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

    # demo route removed per user request

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
