"""
Analytics Service — single source of truth for financial and inventory metrics.

Both seller dashboard and admin reports call these functions,
ensuring the numbers never diverge.
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
    from eacis.models.order import Order, OrderItem
    from eacis.models.product import Product
    from eacis.models.refund_transaction import RefundTransaction
    from eacis.models.return_request import ReturnRequest
    from eacis.models.installment import InstallmentPlan, InstallmentSchedule
    from eacis.models.inventory import StockMovement
except Exception:
    try:
        from ..models.order import Order, OrderItem
        from ..models.product import Product
        from ..models.refund_transaction import RefundTransaction
        from ..models.return_request import ReturnRequest
        from ..models.installment import InstallmentPlan, InstallmentSchedule
        from ..models.inventory import StockMovement
    except Exception:
        from models.order import Order, OrderItem
        from models.product import Product
        from models.refund_transaction import RefundTransaction
        from models.return_request import ReturnRequest
        from models.installment import InstallmentPlan, InstallmentSchedule
        from models.inventory import StockMovement


def get_financial_metrics(seller_id=None, days=30):
    """
    Returns a dict with financial KPIs for dashboards.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # ── Base order query ───────────────────────────────────────────────────
    order_q = Order.query.filter(Order.created_at >= cutoff)
    if seller_id:
        seller_order_ids = (
            db.session.query(OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(Product.seller_id == seller_id)
            .distinct()
            .subquery()
        )
        order_q = order_q.filter(Order.id.in_(db.session.query(seller_order_ids)))

    orders = order_q.filter(Order.status.in_(['paid', 'packed', 'shipped', 'delivered'])).all()
    gross_revenue = sum(float(o.total or 0) for o in orders)
    discount_total = sum(float(o.discount or 0) for o in orders)
    order_count = len(orders)

    # ── Refund total ───────────────────────────────────────────────────────
    refund_q = (
        db.session.query(db.func.coalesce(db.func.sum(RefundTransaction.amount), 0))
        .join(ReturnRequest, ReturnRequest.id == RefundTransaction.return_request_id)
        .filter(RefundTransaction.status == 'processed')
    )
    if seller_id:
        refund_q = refund_q.filter(ReturnRequest.order_id.in_(
            db.session.query(OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(Product.seller_id == seller_id)
            .distinct()
        ))
    refund_total = float(refund_q.scalar() or 0)

    net_revenue = gross_revenue - refund_total
    aov = round(net_revenue / order_count, 2) if order_count > 0 else 0.0

    # ── Settlement info ────────────────────────────────────────────────────
    pending_settlement = 0.0
    pending_order_count = 0
    if seller_id:
        unsettled_q = Order.query.filter(Order.status.in_(['paid', 'packed', 'shipped']))
        seller_u_ids = (
            db.session.query(OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(Product.seller_id == seller_id)
            .distinct().subquery()
        )
        unsettled_orders = unsettled_q.filter(Order.id.in_(db.session.query(seller_u_ids))).all()
        pending_settlement = sum(float(o.total or 0) for o in unsettled_orders)
        pending_order_count = len(unsettled_orders)

    # ── Daily series ───────────────────────────────────────────────────────
    daily_series = []
    if orders:
        from collections import defaultdict
        daily = defaultdict(lambda: {'revenue': 0.0, 'count': 0})
        for o in orders:
            day_key = o.created_at.strftime('%Y-%m-%d') if o.created_at else 'unknown'
            daily[day_key]['revenue'] += float(o.total or 0)
            daily[day_key]['count'] += 1
        for day in sorted(daily.keys(), reverse=True):
            daily_series.append({
                'date': day, 
                'revenue': round(daily[day]['revenue'], 2),
                'count': daily[day]['count']
            })

    # ── Top products ───────────────────────────────────────────────────────
    top_products_q = (
        db.session.query(
            Product.name,
            db.func.sum(OrderItem.quantity).label('units_sold'),
            db.func.sum(OrderItem.subtotal).label('revenue'),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= cutoff, Order.status.in_(['paid', 'packed', 'shipped', 'delivered']))
    )
    if seller_id:
        top_products_q = top_products_q.filter(Product.seller_id == seller_id)
    top_products_q = top_products_q.group_by(Product.name).order_by(db.desc('revenue')).limit(5)
    top_products = [
        {'name': r.name, 'units_sold': int(r.units_sold or 0), 'revenue': float(r.revenue or 0)}
        for r in top_products_q.all()
    ]

    # ── Top categories ─────────────────────────────────────────────────────
    top_categories_q = (
        db.session.query(
            Product.category,
            db.func.sum(OrderItem.subtotal).label('revenue'),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= cutoff, Order.status.in_(['paid', 'packed', 'shipped', 'delivered']))
    )
    if seller_id:
        top_categories_q = top_categories_q.filter(Product.seller_id == seller_id)
    top_categories_q = top_categories_q.group_by(Product.category).order_by(db.desc('revenue')).limit(5)
    top_categories = []
    for r in top_categories_q.all():
        cat_rev = float(r.revenue or 0)
        share = round(cat_rev / gross_revenue * 100, 1) if gross_revenue > 0 else 0.0
        top_categories.append({'category': r.category or 'Uncategorized', 'revenue': cat_rev, 'share': share})

    # ── Pending installment revenue ────────────────────────────────────────
    pending_installment = 0.0
    if seller_id:
        pending_rows = (
            db.session.query(db.func.coalesce(db.func.sum(InstallmentSchedule.amount), 0))
            .join(InstallmentPlan, InstallmentPlan.id == InstallmentSchedule.plan_id)
            .join(Order, Order.id == InstallmentPlan.order_id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(
                Product.seller_id == seller_id,
                InstallmentSchedule.status.in_(['pending', 'past_due']),
            )
            .scalar()
        )
        pending_installment = float(pending_rows or 0)

    refund_rate = (refund_total / gross_revenue * 100) if gross_revenue > 0 else 0.0

    return {
        'gross_revenue': round(gross_revenue, 2),
        'net_revenue': round(net_revenue, 2),
        'discount_total': round(discount_total, 2),
        'refund_total': round(refund_total, 2),
        'total_orders': order_count,
        'avg_order_value': aov,
        'refund_rate': round(refund_rate, 1),
        'pending_settlement': round(pending_settlement, 2),
        'pending_order_count': pending_order_count,
        'daily_series': daily_series,
        'top_products': top_products,
        'top_categories': top_categories,
        'pending_installment_revenue': round(pending_installment, 2),
    }


def get_inventory_metrics(seller_id):
    """
    Returns a dict with inventory health KPIs for the seller.
    """
    products_q = Product.query.filter(Product.seller_id == seller_id)
    total_products = products_q.count()
    
    # Financial valuation: SUM(stock * price)
    total_stock_value = sum(float((p.stock or 0) * (p.price or 0)) for p in products_q.all())

    # Low stock: items at or below threshold
    # Note: Using attribute directly, assuming 'low_stock_threshold' exists on Product
    low_stock_items = [p for p in products_q.all() if (p.stock or 0) <= (getattr(p, 'low_stock_threshold', 5) or 5)]
    out_of_stock_count = sum(1 for p in products_q.all() if (p.stock or 0) <= 0)

    # 30d Movements
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    movements_q = (
        StockMovement.query.join(Product)
        .filter(Product.seller_id == seller_id, StockMovement.created_at >= cutoff_30d)
    )
    movement_count_30d = movements_q.count()
    recent_movements = movements_q.order_by(StockMovement.created_at.desc()).limit(10).all()

    # Sell-through Rate: (Units Sold / (Units Sold + Remaining Stock)) over 30 days
    sold_30d = (
        db.session.query(db.func.sum(OrderItem.quantity))
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Product.seller_id == seller_id, Order.created_at >= cutoff_30d, Order.status != 'cancelled')
        .scalar()
    ) or 0
    remaining_stock = sum((p.stock or 0) for p in products_q.all())
    sell_through_rate = (float(sold_30d) / (float(sold_30d) + remaining_stock) * 100) if (sold_30d + remaining_stock) > 0 else 0.0

    # Stock Coverage: (Stock / Avg Daily Velocity)
    avg_daily_velocity = float(sold_30d) / 30.0
    avg_coverage_days = (remaining_stock / avg_daily_velocity) if avg_daily_velocity > 0 else None

    # Aging SKUs: Products with NO sales in 90 days but have stock
    cutoff_90d = datetime.utcnow() - timedelta(days=90)
    sold_sku_ids_90d = (
        db.session.query(Product.id)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Product.seller_id == seller_id, Order.created_at >= cutoff_90d)
        .distinct().all()
    )
    sold_sku_ids_90d = [r[0] for r in sold_sku_ids_90d]
    aging_skus_count = sum(1 for p in products_q.all() if p.id not in sold_sku_ids_90d and (p.stock or 0) > 0)

    # Top velocity products (for Coverage badge)
    top_velocity_rows = (
        db.session.query(
            Product.id,
            db.func.sum(OrderItem.quantity).label('total_sold')
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Product.seller_id == seller_id, Order.created_at >= cutoff_30d)
        .group_by(Product.id).order_by(db.desc('total_sold')).limit(5).all()
    )
    
    top_products_with_coverage = []
    for p_id, total_sold in top_velocity_rows:
        prod = Product.query.get(p_id)
        velocity = float(total_sold) / 30.0
        coverage = (prod.stock / velocity) if velocity > 0 else None
        top_products_with_coverage.append({
            'product': prod,
            'total_sold': int(total_sold),
            'coverage_days': coverage
        })

    return {
        'total_products': total_products,
        'total_stock_value': round(total_stock_value, 2),
        'low_stock_count': len(low_stock_items),
        'out_of_stock_count': out_of_stock_count,
        'movement_count_30d': movement_count_30d,
        'recent_movements': recent_movements,
        'sell_through_rate': round(sell_through_rate, 1),
        'avg_coverage_days': avg_coverage_days,
        'aging_skus_count': aging_skus_count,
        'top_products': top_products_with_coverage,
        'low_stock_items': low_stock_items,
    }
