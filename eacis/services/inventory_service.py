"""
Inventory Service — single point of truth for all stock mutations.

Every public function:
  1. Creates a StockMovement row (audit trail)
  2. Updates Product.stock cache
  3. Returns the created StockMovement

Never modify Product.stock directly in a route — always go through here.
"""
from datetime import datetime, timedelta, timezone

try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db

try:
    from eacis.models.inventory import StockMovement
    from eacis.models.product import Product
except Exception:
    try:
        from ..models.inventory import StockMovement
        from ..models.product import Product
    except Exception:
        from models.inventory import StockMovement
        from models.product import Product


def deduct_stock(product, quantity, reference, actor_id=None):
    """
    Deduct stock on a sale.
    quantity should be a positive int — we store it as negative.
    """
    qty = int(quantity)
    if qty <= 0:
        raise ValueError('Deduction quantity must be positive.')
    if (product.stock or 0) < qty:
        raise ValueError(f'Insufficient stock for {product.name}. Available: {product.stock or 0}.')

    movement = StockMovement(
        product_id=product.id,
        quantity=-qty,
        type='SALE',
        reference=str(reference or ''),
        note=f'Sale deduction of {qty} units',
        created_by=actor_id,
    )
    product.stock = (product.stock or 0) - qty
    db.session.add(movement)
    return movement


def restock(product, quantity, reference, actor_id=None, note=None):
    """
    Restock items (e.g. approved return where items go back to shelf).
    quantity should be a positive int.
    """
    qty = int(quantity)
    if qty <= 0:
        raise ValueError('Restock quantity must be positive.')

    movement = StockMovement(
        product_id=product.id,
        quantity=qty,
        type='RETURN',
        reference=str(reference or ''),
        note=note or f'Restocked {qty} units from return',
        created_by=actor_id,
    )
    product.stock = (product.stock or 0) + qty
    db.session.add(movement)
    return movement


def restore_on_cancel(product, quantity, reference, actor_id=None):
    """
    Restore stock when an order is cancelled.
    quantity should be a positive int.
    """
    qty = int(quantity)
    if qty <= 0:
        return None

    movement = StockMovement(
        product_id=product.id,
        quantity=qty,
        type='CANCELLATION',
        reference=str(reference or ''),
        note=f'Order cancelled — restored {qty} units',
        created_by=actor_id,
    )
    product.stock = (product.stock or 0) + qty
    db.session.add(movement)
    return movement


def adjust_stock(product, quantity, note, actor_id=None):
    """
    Manual seller adjustment (positive or negative).
    """
    qty = int(quantity)
    if qty == 0:
        raise ValueError('Adjustment quantity cannot be zero.')

    movement = StockMovement(
        product_id=product.id,
        quantity=qty,
        type='ADJUSTMENT',
        reference='MANUAL',
        note=note or f'Manual adjustment of {qty} units',
        created_by=actor_id,
    )
    product.stock = max((product.stock or 0) + qty, 0)
    db.session.add(movement)
    return movement


def get_movement_history(product_id, days=30):
    """Return recent stock movements for a product."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return (
        StockMovement.query
        .filter(
            StockMovement.product_id == product_id,
            StockMovement.created_at >= cutoff,
        )
        .order_by(StockMovement.created_at.desc())
        .all()
    )


def get_inventory_summary(seller_id, days=30):
    """
    Returns a dict with inventory KPIs for a seller:
      total_stock_value, out_of_stock_count, low_stock_list,
      movement_count_30d, daily_units_sold (list of {date, units})
    """
    from sqlalchemy import func

    products = Product.query.filter_by(seller_id=seller_id).all()
    total_stock_value = sum(float(p.price or 0) * int(p.stock or 0) for p in products)
    out_of_stock = [p for p in products if (p.stock or 0) <= 0]
    low_stock = [p for p in products if 0 < (p.stock or 0) <= (p.low_stock_threshold or 5)]

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    product_ids = [p.id for p in products]

    movement_count = 0
    daily_units_sold = []
    if product_ids:
        movement_count = StockMovement.query.filter(
            StockMovement.product_id.in_(product_ids),
            StockMovement.created_at >= cutoff,
        ).count()

        rows = (
            db.session.query(
                db.func.date(StockMovement.created_at).label('day'),
                db.func.sum(db.func.abs(StockMovement.quantity)).label('units'),
            )
            .filter(
                StockMovement.product_id.in_(product_ids),
                StockMovement.type == 'SALE',
                StockMovement.created_at >= cutoff,
            )
            .group_by(db.func.date(StockMovement.created_at))
            .order_by(db.func.date(StockMovement.created_at))
            .all()
        )
        daily_units_sold = [{'date': str(r.day), 'units': int(r.units or 0)} for r in rows]

    return {
        'total_stock_value': total_stock_value,
        'out_of_stock_count': len(out_of_stock),
        'out_of_stock_items': out_of_stock,
        'low_stock_count': len(low_stock),
        'low_stock_items': low_stock,
        'movement_count_30d': movement_count,
        'daily_units_sold': daily_units_sold,
        'total_products': len(products),
    }


def compute_turnover_rate(product_id, days=30):
    """
    Turnover rate = units_sold / average_stock_on_hand over the period.
    Returns a float (higher = faster-moving).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    product = db.session.get(Product, product_id)
    if not product:
        return 0.0

    sold = (
        db.session.query(db.func.sum(db.func.abs(StockMovement.quantity)))
        .filter(
            StockMovement.product_id == product_id,
            StockMovement.type == 'SALE',
            StockMovement.created_at >= cutoff,
        )
        .scalar()
    ) or 0

    avg_stock = max(int(product.stock or 0), 1)  # avoid div-by-zero
    return round(float(sold) / float(avg_stock), 2)
