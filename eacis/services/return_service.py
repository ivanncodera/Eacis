"""
Return Service — policy enforcement, eligibility checks, and abuse scoring.

The return flow:
  1. customer_returns POST → validate_return_eligibility() → create ReturnRequest
  2. seller_returns_update  → approve/deny/refund
  3. After any event        → compute_abuse_score(customer_id)
"""
from datetime import datetime, timedelta

try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db

try:
    from eacis.models.return_request import ReturnRequest
    from eacis.models.return_abuse import ReturnAbuseLog
    from eacis.models.refund_transaction import RefundTransaction
    from eacis.models.order import Order
    from eacis.config import Config
except Exception:
    try:
        from ..models.return_request import ReturnRequest
        from ..models.return_abuse import ReturnAbuseLog
        from ..models.refund_transaction import RefundTransaction
        from ..models.order import Order
        from ..config import Config
    except Exception:
        from models.return_request import ReturnRequest
        from models.return_abuse import ReturnAbuseLog
        from models.refund_transaction import RefundTransaction
        from models.order import Order
        from config import Config


# ── Reason category helpers ────────────────────────────────────────────────

EVIDENCE_REQUIRED_CATEGORIES = frozenset({
    'DEFECTIVE', 'WRONG_ITEM', 'NOT_AS_DESCRIBED', 'DAMAGED_IN_TRANSIT',
})

NON_RESTOCKABLE_CATEGORIES = frozenset({
    'CHANGED_MIND',
})


def evidence_required(reason_category):
    """True if the reason category mandates photo evidence."""
    return (reason_category or '').upper() in EVIDENCE_REQUIRED_CATEGORIES


def is_restockable(reason_category):
    """CHANGED_MIND items go back to shelf only if unopened; default False for that category."""
    return (reason_category or '').upper() not in NON_RESTOCKABLE_CATEGORIES


# ── Eligibility ────────────────────────────────────────────────────────────

def validate_return_eligibility(order, customer_id):
    """
    Returns (is_eligible: bool, reason: str).
    Checks:
      1. Order belongs to customer
      2. Order status is 'delivered'
      3. order.delivered_at is not None
      4. Within return window (delivered_at + RETURN_WINDOW_DAYS)
      5. No existing pending/accepted return for this order
    """
    if not order:
        return False, 'Order not found.'
    if int(getattr(order, 'customer_id', 0) or 0) != int(customer_id):
        return False, 'This order does not belong to you.'
    if order.status != 'delivered':
        return False, f'Only delivered orders can be returned. Current status: {order.status}.'
    if not order.delivered_at:
        return False, 'Delivery date has not been recorded for this order yet.'

    window_days = int(getattr(Config, 'RETURN_WINDOW_DAYS', 7))
    deadline = order.delivered_at.date() + timedelta(days=window_days)
    today = datetime.utcnow().date()
    if today > deadline:
        return False, f'Return window expired. You had until {deadline.strftime("%b %d, %Y")} ({window_days} days from delivery).'

    existing = ReturnRequest.query.filter(
        ReturnRequest.order_id == order.id,
        ReturnRequest.customer_id == customer_id,
        ReturnRequest.status.in_(['pending', 'accepted']),
    ).first()
    if existing:
        return False, f'A return request ({existing.rrt_ref}) is already open for this order.'

    return True, ''


def compute_return_window_deadline(order):
    """Compute the last date a return can be submitted for an order."""
    if not order or not order.delivered_at:
        return None
    window_days = int(getattr(Config, 'RETURN_WINDOW_DAYS', 7))
    return order.delivered_at.date() + timedelta(days=window_days)


# ── Abuse scoring ──────────────────────────────────────────────────────────

def compute_abuse_score(customer_id):
    """
    Compute a rolling abuse score for a customer and upsert ReturnAbuseLog.

    Score formula:
      +2  per return submitted in window
      +3  per CHANGED_MIND return in window
      +5  per refunded_amount / avg_order_value (ratio points, capped at 15)
      −1  per completed order WITHOUT a return in window (good-faith credit)

    Returns (score, is_flagged, is_restricted).
    """
    window_days = int(getattr(Config, 'RETURN_ABUSE_WINDOW_DAYS', 90))
    flag_threshold = int(getattr(Config, 'RETURN_ABUSE_FLAG_THRESHOLD', 10))
    restrict_threshold = int(getattr(Config, 'RETURN_ABUSE_RESTRICT_THRESHOLD', 20))
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    # Returns in window
    returns_in_window = ReturnRequest.query.filter(
        ReturnRequest.customer_id == customer_id,
        ReturnRequest.created_at >= cutoff,
    ).all()

    returns_count = len(returns_in_window)
    changed_mind_count = sum(
        1 for r in returns_in_window
        if (r.reason_category or '').upper() == 'CHANGED_MIND'
    )

    # Refunded amount in window
    return_ids = [r.id for r in returns_in_window]
    refunded_total = 0.0
    if return_ids:
        refunded_total = float(
            db.session.query(db.func.coalesce(db.func.sum(RefundTransaction.amount), 0))
            .filter(
                RefundTransaction.return_request_id.in_(return_ids),
                RefundTransaction.status == 'processed',
            )
            .scalar() or 0
        )

    # Average order value
    avg_order_value = float(
        db.session.query(db.func.coalesce(db.func.avg(Order.total), 0))
        .filter(
            Order.customer_id == customer_id,
            Order.status.in_(['paid', 'delivered']),
            Order.created_at >= cutoff,
        )
        .scalar() or 0
    )

    # Completed orders without returns in window
    completed_orders = Order.query.filter(
        Order.customer_id == customer_id,
        Order.status.in_(['paid', 'delivered']),
        Order.created_at >= cutoff,
    ).count()

    returned_order_ids = set(r.order_id for r in returns_in_window if r.order_id)
    clean_orders = max(completed_orders - len(returned_order_ids), 0)

    # Score computation
    score = 0.0
    score += returns_count * 2
    score += changed_mind_count * 3
    if avg_order_value > 0:
        refund_ratio = refunded_total / avg_order_value
        score += min(refund_ratio * 5, 15.0)  # cap contribution at 15
    score -= clean_orders * 1
    score = max(score, 0.0)

    is_flagged = score >= flag_threshold
    is_restricted = score >= restrict_threshold

    # Build human-readable flag reason
    reasons = []
    if returns_count >= 3:
        reasons.append(f'{returns_count} returns in {window_days} days')
    if changed_mind_count >= 2:
        reasons.append(f'{changed_mind_count} "changed mind" returns')
    if avg_order_value > 0 and refunded_total > avg_order_value * 2:
        reasons.append(f'Refunded ₱{refunded_total:,.2f} ({refunded_total/avg_order_value:.1f}× avg order)')
    flag_reason = '; '.join(reasons) if reasons else None

    # Upsert
    log = ReturnAbuseLog.query.filter_by(customer_id=customer_id).first()
    if not log:
        log = ReturnAbuseLog(customer_id=customer_id)
        db.session.add(log)

    log.abuse_score = round(score, 2)
    log.is_flagged = is_flagged
    # Only escalate to restricted, never auto-unrestrict
    # (admin must manually clear restriction)
    if is_restricted:
        log.is_restricted = True
    log.flag_reason = flag_reason
    log.last_computed = datetime.utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return score, is_flagged, is_restricted


def get_customer_abuse_score(customer_id):
    """
    Retrieve the current abuse score for a customer.
    Returns 0.0 if no score has been computed yet.
    """
    if not customer_id:
        return 0.0
    log = ReturnAbuseLog.query.filter_by(customer_id=customer_id).first()
    return float(log.abuse_score if log else 0.0)


def is_customer_restricted(customer_id):
    """Return True if customer is currently restricted from submitting returns."""
    if not customer_id:
        return False
    log = ReturnAbuseLog.query.filter_by(customer_id=customer_id).first()
    return bool(log and getattr(log, 'is_restricted', False))


import uuid
import random
import string

def generate_rrt_ref():
    """Generate a unique reference for the return request."""
    prefix = "RRT"
    timestamp = datetime.utcnow().strftime("%y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_str}"

def generate_refund_ref():
    """Generate a unique reference for the refund transaction."""
    return f"RFND-{uuid.uuid4().hex[:8].upper()}"

def create_return_request(customer_id, order_id, reason_category, description, evidence_urls=None, other_reason=None):
    """
    Creates a new return request after validating eligibility.
    """
    order = Order.query.get(order_id)
    is_eligible, reason = validate_return_eligibility(order, customer_id)
    if not is_eligible:
        return None, reason

    if is_customer_restricted(customer_id):
        return None, "Your account is restricted from submitting new returns due to high abuse score."

    # Build a human-readable legacy 'reason' field. If the user provided
    # a free-text 'other_reason', include it for future audits.
    reason_display = reason_category or ''
    if reason_display and reason_display.upper() == 'OTHER' and other_reason:
        reason_display = f"OTHER: {other_reason}"

    rrt = ReturnRequest(
        rrt_ref=generate_rrt_ref(),
        order_id=order_id,
        customer_id=customer_id,
        reason=reason_display,  # mapping category to legacy reason field
        description=description,
        evidence_urls=evidence_urls or [],
        status='pending'
    )
    
    # phase 2 fields via duck-typing for future proofing
    # Keep backward-compatible structured field if DB has it
    if hasattr(rrt, 'reason_category'): rrt.reason_category = reason_category
    # If DB has an explicit 'other_reason' field in the future, set it too
    if other_reason and hasattr(rrt, 'other_reason'):
        rrt.other_reason = other_reason
    if hasattr(rrt, 'window_deadline'): rrt.window_deadline = compute_return_window_deadline(order)

    db.session.add(rrt)
    db.session.commit()
    
    compute_abuse_score(customer_id)
    return rrt, "Return request submitted successfully."

def update_return_status(rrt_id, status, seller_notes=None):
    """
    Transitions a return request through its lifecycle.
    """
    rrt = ReturnRequest.query.get(rrt_id)
    if not rrt:
        return False, "Return request not found."

    allowed_transitions = {
        'pending': ['accepted', 'rejected'],
        'accepted': ['refund_requested', 'refunded'],
        'rejected': [],
        'refund_requested': ['refunded'],
        'refunded': []
    }

    if status not in allowed_transitions.get(rrt.status, []):
        return False, f"Cannot transition from {rrt.status} to {status}."

    rrt.status = status
    if seller_notes:
        rrt.seller_notes = seller_notes
    
    if status in ['accepted', 'refunded']:
        rrt.resolved_at = datetime.utcnow()

    db.session.commit()
    compute_abuse_score(rrt.customer_id)
    return True, f"Status updated to {status}."

def process_refund(rrt_id, seller_id=None, amount=None, method='original_payment_method'):
    """
    Finalizes a return by processing a refund.
    Correctly handles points deduction and stock restoration.
    """
    # Reload the request inside a DB-controlled transaction and use a savepoint
    rrt = ReturnRequest.query.get(rrt_id)
    if not rrt:
        return False, "Return request not found."

    # Only accept refunds for accepted/refund_requested states (but allow idempotent handling)
    if rrt.status not in ['accepted', 'refund_requested', 'pending']:
        if rrt.status == 'refunded':
            return False, "Refund has already been processed for this request."
        return False, f"Return request not eligible for refund processing (current status: {rrt.status})."

    # If a seller is specified, ensure they actually own items in this return request
    if seller_id is not None:
        try:
            from eacis.models.order import OrderItem
        except Exception:
            try:
                from ..models.order import OrderItem
            except Exception:
                from models.order import OrderItem
        items_check = OrderItem.query.filter_by(order_id=rrt.order_id).all()
        if not any(oi.product and int(oi.product.seller_id or 0) == int(seller_id) for oi in items_check):
            return False, "Seller not authorized to process this refund."

    # 1. Determine Amount
    refund_val = amount
    if refund_val is None:
        refund_val = float(rrt.refund_amount) if getattr(rrt, 'refund_amount', None) else float(getattr(rrt.order, 'total', 0) or 0)
    try:
        refund_val = float(refund_val or 0)
    except Exception:
        refund_val = 0.0

    # Use a nested transaction / savepoint to serialize checks and the creation of the refund transaction.
    from sqlalchemy.exc import IntegrityError
    try:
        with db.session.begin_nested():
            # Attempt to acquire a row lock on the return request where supported.
            try:
                locked_rrt = db.session.query(ReturnRequest).filter_by(id=rrt.id).with_for_update(nowait=False).first()
            except Exception:
                # DB may not support FOR UPDATE; fallback to the already-loaded rrt
                locked_rrt = ReturnRequest.query.get(rrt.id)

            # Re-check for an existing processed refund for idempotency.
            existing_refund = db.session.query(RefundTransaction).filter_by(return_request_id=rrt.id).with_for_update(read=True).first() if hasattr(db.session.query(RefundTransaction), 'with_for_update') else RefundTransaction.query.filter_by(return_request_id=rrt.id).first()
            if existing_refund and getattr(existing_refund, 'status', '') == 'processed':
                return False, "Refund has already been processed for this request."

            # 2. Restock Logic (Only if seller is matching and request is restockable)
            is_restockable_val = getattr(rrt, 'is_restockable', True)
            if is_restockable_val:
                try:
                    from .inventory_service import restock
                except Exception:
                    try:
                        from services.inventory_service import restock
                    except Exception:
                        restock = None

                if restock:
                    from eacis.models.order import OrderItem
                    items = OrderItem.query.filter_by(order_id=rrt.order_id).all()
                    for oi in items:
                        # If seller_id provided, only restock THEIR items
                        if oi.product and (seller_id is None or int(oi.product.seller_id or 0) == int(seller_id)):
                            try:
                                restock(oi.product, oi.quantity, rrt.rrt_ref, seller_id or oi.product.seller_id)
                            except Exception as e:
                                # Log error but don't block the money flow
                                try:
                                    print(f"Restock failed for {rrt.rrt_ref}: {e}")
                                except Exception:
                                    pass

            # 3. Create or update Refund Transaction
            if existing_refund:
                # If an existing non-processed refund exists, update and mark processed
                existing_refund.amount = refund_val
                existing_refund.method = method
                existing_refund.status = 'processed'
                existing_refund.processed_at = datetime.utcnow()
                refund_tx = existing_refund
            else:
                refund_tx = RefundTransaction(
                    refund_ref=generate_refund_ref(),
                    return_request_id=rrt.id,
                    amount=refund_val,
                    method=method,
                    status='processed'
                )
                db.session.add(refund_tx)

            # 4. Update Return Request
            rrt.status = 'refunded'
            rrt.refund_amount = refund_val
            rrt.resolved_at = datetime.utcnow()

            # 5. Deduct Points (to prevent farming)
            customer = rrt.customer
            if customer and hasattr(customer, 'loyalty_points'):
                points_to_deduct = int(float(refund_val) // 100)
                if points_to_deduct > 0:
                    customer.loyalty_points = max(0, customer.loyalty_points - points_to_deduct)
                    # Add transaction log if possible
                    try:
                        from eacis.models.loyalty import LoyaltyTransaction
                        db.session.add(LoyaltyTransaction(
                            user_id=customer.id,
                            type='redeem',
                            points=points_to_deduct,
                            reference=rrt.rrt_ref,
                            note=f"Points reversed due to refund {rrt.rrt_ref}"
                        ))
                    except Exception:
                        pass

            # Flush within the savepoint so DB errors (e.g. constraint violations) are raised here and can be handled.
            db.session.flush()

        # Commit the outer transaction (if not nested inside a caller) — this will persist the nested savepoint.
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return False, 'Could not finalize refund transaction. Please try again.'

        # Recompute abuse score after successful commit
        try:
            compute_abuse_score(rrt.customer_id)
        except Exception:
            # Do not treat compute failures as fatal for the refund flow
            pass

        return True, f"Refund of ₱{refund_val:,.2f} processed and items restocked."
    except IntegrityError:
        db.session.rollback()
        return False, 'A concurrent update prevented refund processing. Please retry.'
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, 'Could not process refund. Please try again.'
