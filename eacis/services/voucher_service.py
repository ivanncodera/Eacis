"""
Voucher Service — enhanced validation with category targeting,
new-customer checks, min-item-count, and stack rules.

Replaces the inline validate_voucher_for_cart() helper.
"""
from datetime import datetime

try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db

try:
    from eacis.models.voucher import Voucher
    from eacis.models.voucher_usage import VoucherUsageLog
    from eacis.models.order import Order
except Exception:
    try:
        from ..models.voucher import Voucher
        from ..models.voucher_usage import VoucherUsageLog
        from ..models.order import Order
    except Exception:
        from models.voucher import Voucher
        from models.voucher_usage import VoucherUsageLog
        from models.order import Order


def validate_and_apply(voucher_code, cart_items, subtotal, customer_id):
    """
    Full voucher validation including new extended rules.

    Returns: (voucher, normalized_code, discount_amount, error_message)
      voucher: the Voucher object or None
      normalized_code: cleaned code string
      discount_amount: float
      error_message: str or None (None = success)

    Checks:
      1. Code exists and is_active
      2. valid_from / valid_until window
      3. max_uses not exceeded
      4. per_user_limit via VoucherUsageLog (accurate audit)
      5. min_order_amount against eligible_subtotal
      6. target_category — only count items matching category
      7. new_customer_only — reject if customer has prior completed orders
      8. min_item_count — cart must have >= N unique items
    """
    normalized = (voucher_code or '').strip().upper()
    if not normalized:
        return None, '', 0.0, None

    voucher = Voucher.query.filter(Voucher.code.ilike(normalized)).first()
    if not voucher:
        return None, '', 0.0, 'Voucher code not found.'
    if not voucher.is_valid():
        return None, '', 0.0, 'Voucher is not active or has expired.'

    # ── max_uses global check ──────────────────────────────────────────────
    if voucher.max_uses is not None and int(voucher.uses_count or 0) >= int(voucher.max_uses):
        return None, '', 0.0, 'Voucher has reached maximum redemptions.'

    # ── per-user limit (use VoucherUsageLog for accuracy) ──────────────────
    if voucher.per_user_limit is not None:
        usage_count = VoucherUsageLog.query.filter_by(
            voucher_id=voucher.id,
            customer_id=customer_id,
        ).count()
        # Fallback: also count via Order.voucher_id for legacy data
        order_count = Order.query.filter_by(
            customer_id=customer_id,
            voucher_id=voucher.id,
        ).count()
        used = max(usage_count, order_count)
        if used >= int(voucher.per_user_limit):
            return None, '', 0.0, 'You have reached your usage limit for this voucher.'

    # Optional extended fields may be missing on legacy schema/model.
    new_customer_only = bool(getattr(voucher, 'new_customer_only', False))
    min_item_count = getattr(voucher, 'min_item_count', 1)
    target_category = getattr(voucher, 'target_category', None)

    # ── new_customer_only ──────────────────────────────────────────────────
    if new_customer_only:
        prior_orders = Order.query.filter(
            Order.customer_id == customer_id,
            Order.status.in_(['paid', 'delivered', 'shipped', 'packed']),
        ).count()
        if prior_orders > 0:
            return None, '', 0.0, 'This voucher is only valid for your first order.'

    # ── min_item_count ─────────────────────────────────────────────────────
    min_items = int(min_item_count or 1)
    unique_item_count = len(cart_items or [])
    if unique_item_count < min_items:
        return None, '', 0.0, f'This voucher requires at least {min_items} item(s) in your cart.'

    # ── Compute eligible subtotal (seller + category scope) ────────────────
    eligible_subtotal = float(subtotal)

    if voucher.seller_id or target_category:
        eligible_subtotal = 0.0
        for line in (cart_items or []):
            product = line.get('product')
            if not product:
                continue
            # Seller scope
            if voucher.seller_id and getattr(product, 'seller_id', None) != voucher.seller_id:
                continue
            # Category scope
            if target_category:
                product_cat = (getattr(product, 'category', '') or '').strip().lower()
                target_cat = str(target_category).strip().lower()
                if product_cat != target_cat:
                    continue
            eligible_subtotal += float(line.get('line_total') or 0)

        if eligible_subtotal <= 0:
            scope_parts = []
            if voucher.seller_id:
                scope_parts.append('a specific seller')
            if target_category:
                scope_parts.append(f'"{target_category}" products')
            scope_desc = ' and '.join(scope_parts)
            return None, '', 0.0, f'This voucher is only valid for {scope_desc} in your cart.'

    # ── min_order_amount ───────────────────────────────────────────────────
    min_amount = float(voucher.min_order_amount or 0)
    if eligible_subtotal < min_amount:
        return None, '', 0.0, f'Voucher requires minimum order of ₱{min_amount:,.2f}.'

    # ── Compute discount ───────────────────────────────────────────────────
    if (voucher.discount_type or '').strip() == 'percent':
        discount = eligible_subtotal * (float(voucher.discount_value or 0) / 100.0)
    else:
        discount = float(voucher.discount_value or 0)

    discount = max(min(discount, eligible_subtotal), 0.0)
    return voucher, voucher.code, float(discount), None


def record_usage(voucher, customer_id, order_id, discount_applied):
    """Log a voucher usage after order is committed."""
    if not voucher:
        return
    log = VoucherUsageLog(
        voucher_id=voucher.id,
        customer_id=customer_id,
        order_id=order_id,
        discount_applied=discount_applied,
        used_at=datetime.utcnow(),
    )
    db.session.add(log)


def can_combine(voucher_a, voucher_b):
    """
    Stack rules:
      - Two seller-scoped vouchers: NEVER
      - Platform (seller_id=None) + seller: only if BOTH have combinable=True
      - Two platform vouchers: NEVER
    """
    if not voucher_a or not voucher_b:
        return True  # nothing to stack
    if voucher_a.id == voucher_b.id:
        return False  # same voucher twice
    a_seller = voucher_a.seller_id is not None
    b_seller = voucher_b.seller_id is not None
    if a_seller and b_seller:
        return False  # two seller vouchers never stack
    if not a_seller and not b_seller:
        return False  # two platform vouchers never stack
    # Mixed: platform + seller — both must be combinable
    return bool(voucher_a.combinable) and bool(voucher_b.combinable)
