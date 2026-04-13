try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime


class InquiryTicket(db.Model):
    __tablename__ = 'inquiry_tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_ref = db.Column(db.String(30), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Enum('low', 'medium', 'high', 'urgent', name='inquiry_priority'), default='medium')
    status = db.Column(db.Enum('open', 'in_progress', 'resolved', 'closed', name='inquiry_status'), default='open')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    customer = db.relationship('User', foreign_keys=[customer_id])
    assignee = db.relationship('User', foreign_keys=[assigned_to])
    order = db.relationship('Order')

    def __repr__(self):
        return f"<InquiryTicket {self.ticket_ref}>"
