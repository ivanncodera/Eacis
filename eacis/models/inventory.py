try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime


class StockMovement(db.Model):
    """
    Audit trail for every stock mutation on a product.

    Design — Event Sourcing lite:
    Every time stock changes (sale, return, restock, cancellation, manual
    adjustment) a row is inserted here.  Product.stock is a *cached* integer
    that must always equal SUM(quantity) of all movements for that product.
    If the cache ever drifts it can be recomputed from this table.

    quantity rules:
      positive (+)  →  stock increases  (RETURN, RESTOCK, CANCELLATION, ADJUSTMENT+)
      negative (−)  →  stock decreases  (SALE, ADJUSTMENT-)
    """
    __tablename__ = 'stock_movements'

    id          = db.Column(db.Integer, primary_key=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity    = db.Column(db.Integer, nullable=False)          # signed; positive=in, negative=out
    type        = db.Column(
        db.Enum('SALE', 'RETURN', 'RESTOCK', 'ADJUSTMENT', 'CANCELLATION',
                name='stock_movement_type'),
        nullable=False,
    )
    reference   = db.Column(db.String(80))    # order_ref, rrt_ref, 'MANUAL', etc.
    note        = db.Column(db.String(255))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    product     = db.relationship('Product', backref=db.backref('stock_movements', lazy='dynamic'))
    actor       = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        sign = '+' if self.quantity >= 0 else ''
        return f'<StockMovement product={self.product_id} {sign}{self.quantity} [{self.type}]>'
