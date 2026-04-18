try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from datetime import datetime


class InquiryReply(db.Model):
    """
    Threaded reply on an InquiryTicket.

    is_internal: if True the reply is a seller-only note (not shown to customer).
    author can be a seller, admin, or customer — checked at the route level.
    """
    __tablename__ = 'inquiry_replies'

    id          = db.Column(db.Integer, primary_key=True)
    ticket_id   = db.Column(db.Integer, db.ForeignKey('inquiry_tickets.id'), nullable=False, index=True)
    author_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)  # internal note vs customer-visible
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket  = db.relationship('InquiryTicket', backref=db.backref('replies', order_by='InquiryReply.created_at'))
    author  = db.relationship('User', foreign_keys=[author_id])

    def __repr__(self):
        internal = ' [internal]' if self.is_internal else ''
        return f'<InquiryReply ticket={self.ticket_id} author={self.author_id}{internal}>'
