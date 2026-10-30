import os

path = os.path.join('eacis', 'app.py')
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. P0-1: LOGIC-01
t1 = """            order.status = 'cancelled'
            db.session.commit()
            return True, f'Order {order_ref} has been cancelled. Stock and benefits restored.'
        except Exception:
            db.session.rollback()
            return False, 'Could not cancel order. Please try again.'

        from eacis.models.return_request import ReturnRequest"""
r1 = """            order.status = 'cancelled'
            db.session.commit()
            return True, f'Order {order_ref} has been cancelled. Stock and benefits restored.'
        except Exception:
            db.session.rollback()
            return False, 'Could not cancel order. Please try again.'

    def finalize_seller_refund(seller, rrt_ref):
        from eacis.models.return_request import ReturnRequest"""
assert t1 in c, "P0-1 target missing"
c = c.replace(t1, r1, 1)

# 2. P0-2: LOGIC-02 (calculate_refund_amount cap)
t2 = """        ratio = scoped_items_subtotal / order_subtotal
        ratio = min(max(ratio, 0.0), 1.0)
        return round(order_total * ratio, 2)"""
r2 = """        ratio = scoped_items_subtotal / order_subtotal
        ratio = min(max(ratio, 0.0), 1.0)
        base_refund = round(order_total * ratio, 2)
        if getattr(order, 'payment_method', '') == 'installment':
            try:
                from eacis.models.installment import InstallmentPlan
                plan = InstallmentPlan.query.filter_by(order_id=order.id).first()
                if plan:
                    actually_paid = sum(float(s.amount or 0) for s in plan.schedules if getattr(s, 'status', '') == 'paid')
                    actually_paid += float(getattr(plan, 'downpayment_amount', 0) or 0)
                    scoped_paid = round(actually_paid * ratio, 2) if seller_id is not None else round(actually_paid, 2)
                    return min(base_refund, scoped_paid)
            except Exception:
                pass
        return base_refund"""
assert t2 in c, "P0-2 target missing"
c = c.replace(t2, r2, 1)

# 3. P0-3: LOGIC-08 (checkout_success points)
t3 = """                placed_at = order.created_at
                earned_points = int(order.total // 100) if order.total else 0
                # Clear KYC session flag after successful order"""
r3 = """                placed_at = order.created_at
                if getattr(order, 'payment_method', '') == 'full_pay':
                    earned_points = int(order.total // 100) if order.total else 0
                else:
                    earned_points = 0
                # Clear KYC session flag after successful order"""
assert t3 in c, "P0-3 target missing"
c = c.replace(t3, r3, 1)

# 4. P0-4 & P0-6: LOGIC-04 & LOGIC-03 in seller_order_detail
t4 = """        if request.method == 'POST':
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
                    return redirect(url_for('seller_order_detail', order_ref=order_ref))"""

r4 = """        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            if action == 'update_status':
                new_status = (request.form.get('status') or '').strip().lower()
                current_status = getattr(order, 'status', '').lower()
                allowed_transitions = {
                    'paid': ['packed'],
                    'packed': ['shipped'],
                    'shipped': ['delivered'],
                    'delivered': [],
                    'cancelled': [],
                    'refunded': [],
                }
                kyc_approved = 'kyc approved' in (order.notes or '').lower() or 'kyc_approved' in (order.notes or '').lower()
                if current_status == 'pending' and order.payment_method == 'installment' and kyc_approved:
                    allowed_transitions['pending'] = ['packed']
                else:
                    allowed_transitions['pending'] = []

                if new_status not in allowed_transitions.get(current_status, []):
                    flash(f'Cannot change order status from {current_status} to {new_status}.', 'error')
                else:
                    try:
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
                return redirect(url_for('seller_order_detail', order_ref=order_ref))"""
assert t4 in c, "P0-4 target missing"
c = c.replace(t4, r4, 1)

# 5. P0-5: LOGIC-05 seller_installment_review
t5 = """            action = (request.form.get('action') or '').strip().lower()
            if action == 'approve':
                try:
                    order.status = 'paid'
                    order.paid_at = datetime.utcnow()
                    db.session.add(order)
                    invoice_err = None
                    try:
                        ensure_invoice_for_order(order)
                    except Exception as ie:
                        invoice_err = str(ie)
                        try:
                            app.logger.exception('Invoice generation failed for order %s', order.order_ref)
                        except Exception:
                            pass
                        # Append an audit note to the order so admins can inspect later
                        try:
                            order.notes = (order.notes or '') + f' | invoice_error={invoice_err}'
                            db.session.add(order)
                        except Exception:
                            pass

                    # Commit the order regardless of invoice generation success to avoid leaving the order in limbo
                    db.session.commit()
                    if invoice_err:
                        flash('Installment order confirmed but invoice generation failed; please review.', 'warning')
                    else:
                        flash('Installment order confirmed and invoices generated.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not confirm the order at this time.', 'error')
                return redirect(url_for('seller_installment_payments'))"""

r5 = """            action = (request.form.get('action') or '').strip().lower()
            if action == 'approve':
                try:
                    order.notes = (order.notes or '') + ' | KYC approved by seller'
                    db.session.add(order)
                    invoice_err = None
                    try:
                        ensure_invoice_for_order(order)
                    except Exception as ie:
                        invoice_err = str(ie)
                        try:
                            app.logger.exception('Invoice generation failed for order %s', order.order_ref)
                        except Exception:
                            pass
                        try:
                            order.notes = (order.notes or '') + f' | invoice_error={invoice_err}'
                            db.session.add(order)
                        except Exception:
                            pass

                    db.session.commit()
                    if invoice_err:
                        flash('Installment KYC approved but invoice generation failed; please review.', 'warning')
                    else:
                        flash('Installment KYC approved. Order is now ready to be packed.', 'success')
                except Exception:
                    db.session.rollback()
                    flash('Could not confirm the order at this time.', 'error')
                return redirect(url_for('seller_installment_payments'))"""
assert t5 in c, "P0-5 target missing"
c = c.replace(t5, r5, 1)

# 6. P0-6: LOGIC-03 seller_payouts & admin_seller_detail
t6_payouts = """        # Compute balances from full datasets (not just the page) so KPIs remain accurate
        delivered_orders = base_q.filter(Order.status == 'delivered').all()
        available_balance = sum(float(o.total or 0) for o in delivered_orders)
        pending_clearance = sum(float(o.total or 0) for o in base_q.filter(Order.status.in_(['paid', 'packed', 'shipped'])).all())

        today = datetime.utcnow().date()"""
r6_payouts = """        def _seller_order_amount(ord_obj, sel_id):
            items = getattr(ord_obj, 'items', None)
            if not items:
                return 0.0
            total_amt = 0.0
            for it in items.all() if hasattr(items, 'all') else items:
                prod = getattr(it, 'product', None)
                if prod and int(getattr(prod, 'seller_id', 0) or 0) == int(sel_id):
                    total_amt += float(getattr(it, 'subtotal', None) or ((getattr(it, 'unit_price', 0) or 0) * (getattr(it, 'quantity', 0) or 0)) or 0)
            return round(total_amt, 2)

        delivered_orders = base_q.filter(Order.status == 'delivered').all()
        available_balance = sum(_seller_order_amount(o, current_user.id) for o in delivered_orders)
        pending_clearance = sum(_seller_order_amount(o, current_user.id) for o in base_q.filter(Order.status.in_(['paid', 'packed', 'shipped'])).all())

        today = datetime.utcnow().date()"""
assert t6_payouts in c, "P0-6 seller_payouts target missing"
c = c.replace(t6_payouts, r6_payouts, 1)

t6_ltv = """        payout_total = 0.0
        for order in orders:
            if order.status in ('delivered', 'paid', 'shipped', 'packed'):
                try:
                    payout_total += float(order.total or 0)
                except Exception:
                    payout_total += 0.0"""
r6_ltv = """        payout_total = 0.0
        for order in orders:
            if order.status in ('delivered', 'paid', 'shipped', 'packed'):
                try:
                    for item in (order.items.all() if hasattr(order.items, 'all') else order.items):
                        if item.product and int(getattr(item.product, 'seller_id', 0) or 0) == int(seller.id):
                            payout_total += float(item.subtotal or ((item.unit_price or 0) * (item.quantity or 0)) or 0)
                except Exception:
                    pass"""
assert t6_ltv in c, "P0-6 admin_seller_detail target missing"
c = c.replace(t6_ltv, r6_ltv, 1)

# 7. P0-7 & P1-15: SEC-02 & SEC-01 in serve_permit and add serve_return_upload
t7 = """        # Authorization: admins and sellers may view any permit; customers may only view their own KYC files
        role = getattr(current_user, 'role', None)
        if role == 'customer':
            expected_prefix = f"kyc_cust{current_user.id}_"
            if not filepart.startswith(expected_prefix):
                abort(404)
        elif role in ('seller', 'admin'):
            # seller/admin allowed to view for review purposes
            pass
        else:
            abort(404)

        try:
            if not os.path.exists(os.path.join(base, filepart)):
                abort(404)
            return send_from_directory(base, filepart)"""

r7 = """        role = getattr(current_user, 'role', None)
        if role == 'admin':
            pass
        elif role == 'customer':
            expected_prefix = f"kyc_cust{current_user.id}_"
            owns_doc = filepart.startswith(expected_prefix) or (current_user.business_permit_path and filepart in current_user.business_permit_path)
            if not owns_doc:
                abort(403)
        elif role == 'seller':
            owns_permit = any(
                getattr(current_user, col, None) and filepart in getattr(current_user, col)
                for col in ('business_permit_path', 'barangay_permit_path', 'mayors_permit_path')
            )
            if owns_permit:
                pass
            elif filepart.startswith('kyc_cust'):
                try:
                    import re
                    m = re.match(r'kyc_cust(\\d+)_', filepart)
                    cust_id = int(m.group(1)) if m else None
                    if cust_id:
                        from eacis.models.order import Order, OrderItem
                        from eacis.models.product import Product
                        has_order = (
                            db.session.query(OrderItem.id)
                            .join(Order, Order.id == OrderItem.order_id)
                            .join(Product, Product.id == OrderItem.product_id)
                            .filter(Order.customer_id == cust_id, Product.seller_id == current_user.id)
                            .first()
                        ) is not None
                        if not has_order:
                            abort(403)
                    else:
                        abort(403)
                except Exception:
                    abort(403)
            else:
                abort(403)
        else:
            abort(403)

        try:
            if not os.path.exists(os.path.join(base, filepart)):
                abort(404)
            return send_from_directory(base, filepart)
        except Exception:
            abort(404)

    @app.route('/uploads/returns/<path:filename>')
    def serve_return_upload(filename):
        from flask_login import current_user
        from flask import send_from_directory
        if not (current_user and getattr(current_user, 'is_authenticated', False)):
            abort(404)

        filepart = filename.split('returns/', 1)[-1]
        safe_name = secure_filename(filepart)
        base = os.path.join(app.instance_path, 'uploads', 'returns')

        role = getattr(current_user, 'role', None)
        if role == 'admin':
            pass
        else:
            from eacis.models.return_request import ReturnRequest
            from eacis.models.order import OrderItem
            from eacis.models.product import Product

            rrt = ReturnRequest.query.filter(ReturnRequest.evidence_urls.like(f"%{safe_name}%")).first()
            if not rrt:
                import re
                m = re.match(r'cust(\\d+)_', safe_name)
                cust_id = int(m.group(1)) if m else None
                if role == 'customer' and cust_id == current_user.id:
                    pass
                else:
                    abort(403)
            else:
                if role == 'customer':
                    if rrt.customer_id != current_user.id:
                        abort(403)
                elif role == 'seller':
                    seller_on_order = (
                        db.session.query(OrderItem.id)
                        .join(Product, Product.id == OrderItem.product_id)
                        .filter(OrderItem.order_id == rrt.order_id, Product.seller_id == current_user.id)
                        .first()
                    ) is not None
                    if not seller_on_order:
                        abort(403)
                else:
                    abort(403)

        return send_from_directory(base, safe_name)"""
assert t7 in c, "P0-7 target missing"
c = c.replace(t7, r7, 1)

# 8. P0-10: UI-02 (admin_dashboard OTP stats)
t8 = """            'otp_success_rate': otp_success_rate,
            'otp_top_purposes': otp_top_purposes,"""
r8 = """            'otp_success_rate': otp_success_rate,
            'otp_verify_rate_24h': (otp_success_rate / 100.0) if otp_sent_today else 1.0,
            'otp_sent_24h': otp_sent_today,
            'otp_top_purposes': otp_top_purposes,"""
assert t8 in c, "P0-10 target missing"
c = c.replace(t8, r8, 1)

# 9. P0-11 & P0-12: LOGIC-06 & LOGIC-07 in checkout()
t9_voucher = """                if voucher:
                    voucher.uses_count = int(voucher.uses_count or 0) + 1"""
r9_voucher = """                if voucher:
                    voucher.uses_count = int(voucher.uses_count or 0) + 1
                    try:
                        from eacis.services import voucher_service as VchSvc
                        if VchSvc:
                            VchSvc.record_usage(
                                voucher=voucher,
                                customer_id=current_user.id,
                                order_id=order.id,
                                discount_amount=voucher_discount
                            )
                    except Exception:
                        pass"""
assert t9_voucher in c, "P0-12 voucher target missing"
c = c.replace(t9_voucher, r9_voucher, 1)

t9_cart = """                if order.status == 'paid':
                    try:
                        ensure_invoice_for_order(order)
                    except Exception as ie:
                        try:
                            app.logger.exception('Invoice generation failed, attaching note to order')
                        except Exception:
                            pass
                        order.notes = (getattr(order, 'notes', '') or '') + f" | invoice_error: {str(ie)}"

                cart.items = []
                cart.voucher_code = None
                db.session.commit()"""

r9_cart = """                if order.status == 'paid':
                    try:
                        ensure_invoice_for_order(order)
                    except Exception as ie:
                        try:
                            app.logger.exception('Invoice generation failed, attaching note to order')
                        except Exception:
                            pass
                        order.notes = (getattr(order, 'notes', '') or '') + f" | invoice_error: {str(ie)}"

                purchased_item_keys = set()
                for line in cart_items:
                    prod = line.get('product')
                    if prod:
                        purchased_item_keys.add(str(prod.id))
                        purchased_item_keys.add(str(getattr(prod, 'product_ref', '')))
                    if line.get('product_id'):
                        purchased_item_keys.add(str(line['product_id']))

                remaining_items = []
                for entry in (cart.items or []):
                    entry_pid = str(entry.get('product_id', ''))
                    if entry_pid not in purchased_item_keys:
                        remaining_items.append(entry)

                cart.items = remaining_items
                cart.voucher_code = None
                db.session.commit()"""
assert t9_cart in c, "P0-11 cart target missing"
c = c.replace(t9_cart, r9_cart, 1)

# 10. P0-13: LOGIC-09 in seller_analytics and admin_reports
t10_sel = """        rows = db.session.query(OrderItem, Product, Order).join(Product, Product.id == OrderItem.product_id).join(Order, Order.id == OrderItem.order_id).filter(Product.seller_id == current_user.id).all()"""
r10_sel = """        VALID_REVENUE_STATUSES = ('paid', 'packed', 'shipped', 'delivered')
        rows = (
            db.session.query(OrderItem, Product, Order)
            .join(Product, Product.id == OrderItem.product_id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Product.seller_id == current_user.id, Order.status.in_(VALID_REVENUE_STATUSES))
            .all()
        )"""
assert t10_sel in c, "P0-13 seller_analytics target missing"
c = c.replace(t10_sel, r10_sel, 1)

t10_adm = """        def order_total_since(dt):
            total = 0.0
            rows = Order.query.filter(Order.created_at >= dt).all()"""
r10_adm = """        def order_total_since(dt):
            total = 0.0
            VALID_REVENUE_STATUSES = ('paid', 'packed', 'shipped', 'delivered')
            rows = Order.query.filter(Order.created_at >= dt, Order.status.in_(VALID_REVENUE_STATUSES)).all()"""
assert t10_adm in c, "P0-13 admin_reports target missing"
c = c.replace(t10_adm, r10_adm, 1)

# 11. P0-14: LOGIC-12 sync_overdue_schedules on admin_dashboard
t11 = """    @app.route('/admin/dashboard')
    def admin_dashboard():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))"""
r11 = """    @app.route('/admin/dashboard')
    def admin_dashboard():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'admin'):
            return redirect(url_for('auth_login', next=request.path))

        try:
            from eacis.services import installment_service as InstSvc
            if InstSvc:
                InstSvc.sync_overdue_schedules()
                db.session.commit()
        except Exception:
            db.session.rollback()"""
assert t11 in c, "P0-14 target missing"
c = c.replace(t11, r11, 1)

# 12. P1-15: SEC-01 seller inquiry detail 403
t12 = """        ticket = InquiryTicket.query.filter_by(ticket_ref=ticket_ref).first()
        if not ticket:
            flash('Inquiry not found.', 'error')
            return redirect(url_for('seller_customer_inquiries'))"""
r12 = """        ticket = InquiryTicket.query.filter_by(ticket_ref=ticket_ref).first()
        if not ticket:
            flash('Inquiry not found.', 'error')
            return redirect(url_for('seller_customer_inquiries'))

        if ticket.assigned_to and int(ticket.assigned_to) != int(current_user.id):
            abort(403)"""
assert t12 in c, "P1-15 target missing"
c = c.replace(t12, r12, 1)

# 13. P1-16: SEC-03 suspended seller portal guard
t13 = """            verification_status = (getattr(current_user, 'seller_verification_status', '') or '').lower()
            if verification_status in ('pending', 'rejected'):"""
r13 = """            verification_status = (getattr(current_user, 'seller_verification_status', '') or '').lower()
            if verification_status == 'suspended' or not getattr(current_user, 'is_active', True):
                flash('Your seller account has been suspended by administration. Access to portal features is revoked.', 'error')
                return render_template('errors/seller_suspended.html'), 403

            if verification_status in ('pending', 'rejected'):"""
assert t13 in c, "P1-16 target missing"
c = c.replace(t13, r13, 1)

# 14. P1-17: SEC-04 safe redirect helper in login & otp
t14_login = """                nxt = request.args.get('next') or request.form.get('next') or ''
                def safe_redirect_for_role(role, target):
                    if not target or not target.startswith('/'):
                        return None
                    if target.startswith('/admin') and role != 'admin':
                        return None
                    if target.startswith('/seller') and role != 'seller':
                        return None
                    if target.startswith('/customer') and role != 'customer':
                        return None
                    return target"""

r14_login = """                nxt = request.args.get('next') or request.form.get('next') or ''
                from urllib.parse import urlsplit
                def is_safe_redirect(target):
                    if not target or not isinstance(target, str):
                        return False
                    if target.startswith('//') or target.startswith('/\\\\') or target.startswith('\\\\'):
                        return False
                    if not target.startswith('/'):
                        return False
                    parts = urlsplit(target)
                    return parts.netloc == '' and parts.scheme == ''

                def safe_redirect_for_role(role, target):
                    if not is_safe_redirect(target):
                        return None
                    if target.startswith('/admin') and role != 'admin':
                        return None
                    if target.startswith('/seller') and role != 'seller':
                        return None
                    if target.startswith('/customer') and role != 'customer':
                        return None
                    return target"""
assert t14_login in c, "P1-17 login target missing"
c = c.replace(t14_login, r14_login, 1)

t14_otp = """            target = next_url or (url_for('seller_dashboard') if user and user.role == 'seller' else url_for('shop'))"""
r14_otp = """            from urllib.parse import urlsplit
            def _is_safe(u):
                if not u or not isinstance(u, str) or u.startswith('//') or u.startswith('/\\\\') or not u.startswith('/'):
                    return False
                parts = urlsplit(u)
                return parts.netloc == '' and parts.scheme == ''
            target = next_url if _is_safe(next_url) else None
            if not target:
                target = url_for('seller_dashboard') if user and user.role == 'seller' else url_for('shop')"""
assert t14_otp in c, "P1-17 otp target missing"
c = c.replace(t14_otp, r14_otp, 1)

# 15. P1-18: SEC-09 unverified customers redirected to verify at checkout
t15 = """    @app.route('/customer/checkout', methods=['GET', 'POST'])
    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))"""
r15 = """    @app.route('/customer/checkout', methods=['GET', 'POST'])
    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        from flask_login import current_user
        if not (current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) == 'customer'):
            return redirect(url_for('auth_login', next=request.path))

        if not getattr(current_user, 'email_verified_at', None):
            flash('Please verify your email address to proceed to checkout.', 'warning')
            return redirect(url_for('auth_otp_verify'))"""
assert t15 in c, "P1-18 target missing"
c = c.replace(t15, r15, 1)

# 16. P2-22: UI-03 Jinja filter for peso currency
peso_filter_code = """
    @app.template_filter('peso')
    def peso_filter(val):
        try:
            return f"₱{float(val or 0):,.2f}"
        except Exception:
            return "₱0.00"
"""
t_filter_anchor = "    app.can_view_product_id = can_view_product_id"
assert t_filter_anchor in c, "Filter anchor missing"
c = c.replace(t_filter_anchor, t_filter_anchor + peso_filter_code, 1)

# Write updated app.py
with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print("Applied all P0, P1, and P2 backend fixes to app.py successfully!")
