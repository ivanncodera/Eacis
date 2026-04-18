"""
Review service: create/update/delete reviews and toggle stars.
"""
from datetime import datetime

try:
    from eacis.extensions import db
    from eacis.models.review import Review
    from eacis.models.product_star import ProductStar
except Exception:
    from ..extensions import db
    from ..models.review import Review
    from ..models.product_star import ProductStar

# Helper: check whether the user has a delivered order containing the product
def has_user_received_product(user_id, product_id):
    """Return True if the user has a delivered order containing the product."""
    try:
        # import locally to avoid circular imports
        try:
            from ..models.order import Order, OrderItem
        except Exception:
            from models.order import Order, OrderItem
        q = db.session.query(OrderItem).join(Order, OrderItem.order_id == Order.id).filter(
            Order.customer_id == user_id,
            Order.status == 'delivered',
            OrderItem.product_id == product_id,
        )
        return q.count() > 0
    except Exception:
        return False


def create_or_update_review(user_id, product_id, rating, title=None, body=None, is_anonymous=False, require_purchase=False):
    """Create or update a user's review for a product.

    Returns (review_obj, error_message)
    """
    try:
        rating = int(rating)
    except Exception:
        return None, 'Invalid rating value.'
    if rating < 1 or rating > 5:
        return None, 'Rating must be between 1 and 5.'

    # If this workflow requires purchase verification, ensure user received the product
    if require_purchase:
        if not has_user_received_product(user_id, product_id):
            return None, 'Only customers who purchased and received this product may submit a review.'

    # find existing
    existing = Review.query.filter_by(product_id=product_id, user_id=user_id).first()
    if existing:
        existing.rating = rating
        existing.title = title or existing.title
        existing.body = body or existing.body
        existing.is_anonymous = bool(is_anonymous)
        # capture reviewer snapshot when not anonymous
        if not existing.is_anonymous:
            try:
                from ..models.user import User
            except Exception:
                from models.user import User
            user = User.query.get(user_id)
            existing.reviewer_name = (getattr(user, 'computed_full_name', None) or getattr(user, 'full_name', None) or getattr(user, 'email', None)) if user else existing.reviewer_name
        else:
            existing.reviewer_name = None
        existing.updated_at = datetime.utcnow()
        try:
            db.session.commit()
            return existing, None
        except Exception as e:
            db.session.rollback()
            return None, 'Could not update review.'

    # create new
    # determine reviewer name snapshot
    reviewer_name = None
    if not is_anonymous:
        try:
            from ..models.user import User
        except Exception:
            from models.user import User
        user = User.query.get(user_id)
        reviewer_name = (getattr(user, 'computed_full_name', None) or getattr(user, 'full_name', None) or getattr(user, 'email', None)) if user else None

    rv = Review(
        product_id=product_id,
        user_id=user_id,
        rating=rating,
        title=title,
        body=body,
        is_anonymous=bool(is_anonymous),
        reviewer_name=reviewer_name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    try:
        db.session.add(rv)
        db.session.commit()
        return rv, None
    except Exception:
        db.session.rollback()
        return None, 'Could not create review.'


def delete_review(user_id, review_id):
    r = Review.query.get(review_id)
    if not r or int(r.user_id or 0) != int(user_id):
        return False, 'Not authorized or review not found.'
    try:
        db.session.delete(r)
        db.session.commit()
        return True, None
    except Exception:
        db.session.rollback()
        return False, 'Could not delete review.'


def toggle_star(user_id, product_id, require_purchase=False):
    # Optionally enforce that only customers who received the product may star it
    if require_purchase:
        try:
            if not has_user_received_product(user_id, product_id):
                return None, 'Only customers who purchased and received this product may star it.'
        except Exception:
            # if helper fails, fall through and let DB operations decide
            pass

    star = ProductStar.query.filter_by(product_id=product_id, user_id=user_id).first()
    if star:
        try:
            db.session.delete(star)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return None, 'Could not remove star.'
        starred = False
    else:
        new_star = ProductStar(product_id=product_id, user_id=user_id)
        try:
            db.session.add(new_star)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return None, 'Could not add star.'
        starred = True

    count = ProductStar.query.filter_by(product_id=product_id).count()
    return {'starred': starred, 'stars_count': count}, None


def get_aggregate(product_id):
    # returns {'avg': float, 'count': int}
    try:
        agg = db.session.query(db.func.count(Review.id), db.func.avg(Review.rating)).filter(
            Review.product_id == product_id,
            Review.is_approved.is_(True)
        ).one()
        count, avg = agg[0], agg[1]
        return {'count': int(count or 0), 'avg': float(avg or 0.0)}
    except Exception:
        return {'count': 0, 'avg': 0.0}


def get_reviews(product_id, limit=10, offset=0):
    q = Review.query.filter_by(product_id=product_id, is_approved=True).order_by(Review.created_at.desc())
    items = q.offset(offset).limit(limit).all()
    return items
