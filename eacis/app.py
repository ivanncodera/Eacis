from flask import Flask, render_template
from flask import redirect, url_for, request, jsonify
from flask import flash, session
import time
# If run directly as a script (``python eacis/app.py``), ensure package imports work
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
                if User.query.count() == 0:
                    u1 = User(email='customer@example.com', role='customer', full_name='Dev Customer')
                    u1.set_password('password')
                    u2 = User(email='seller@example.com', role='seller', full_name='Dev Seller')
                    u2.set_password('password')
                    u3 = User(email='admin@example.com', role='admin', full_name='Dev Admin')
                    u3.set_password('password')
                    db.session.add_all([u1,u2,u3])
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
                if portal == 'customer' and user.role != 'customer':
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

    @app.route('/customer/cart')
    @app.route('/cart')
    def cart():
        return render_template('customer/cart.html')

    @app.route('/customer/checkout')
    @app.route('/checkout')
    def checkout():
        return render_template('customer/checkout.html')

    @app.route('/customer/checkout/success')
    def checkout_success():
        return render_template('customer/checkout_success.html')

    @app.route('/customer/orders')
    def customer_orders():
        return render_template('customer/orders.html')

    @app.route('/customer/returns')
    def customer_returns():
        return render_template('customer/returns.html')

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
        return render_template('seller/products.html')

    @app.route('/seller/products/new')
    @app.route('/seller/products/create')
    @app.route('/seller/product/create')
    def seller_product_create():
        return render_template('seller/product_form.html')

    @app.route('/seller/products/<ref>')
    @app.route('/seller/products/<ref>/edit')
    def seller_product_detail(ref):
        return render_template('seller/product_form.html', ref=ref)

    @app.route('/seller/inventory')
    def seller_inventory():
        return render_template('seller/inventory.html')

    @app.route('/seller/orders')
    def seller_orders():
        return render_template('seller/orders.html')

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
        return render_template('seller/order_detail.html', order_ref=order_ref)

    @app.route('/seller/returns')
    def seller_returns():
        return render_template('seller/returns.html')

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

    @app.route('/admin/products')
    def admin_products():
        return render_template('admin/products.html')

    @app.route('/admin/customers')
    def admin_customers():
        return render_template('admin/customers.html')

    @app.route('/admin/settings')
    def admin_settings():
        return render_template('admin/settings.html')

    @app.route('/admin/reports')
    def admin_reports():
        return render_template('admin/reports.html')

    # demo route removed per user request

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
