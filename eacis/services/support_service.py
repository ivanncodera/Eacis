"""
Support Service — Triage engine and Inquiry lifecycle management.
"""
from datetime import datetime
import uuid

try:
    from eacis.extensions import db
    from eacis.models.inquiry_ticket import InquiryTicket
    from eacis.models.inquiry_reply import InquiryReply
    from eacis.models.order import Order, OrderItem
except Exception:
    from extensions import db
    from models.inquiry_ticket import InquiryTicket
    from models.inquiry_reply import InquiryReply
    from models.order import Order, OrderItem

def generate_ticket_ref():
    return f"TK-{uuid.uuid4().hex[:8].upper()}"

def create_ticket(customer_id, subject, description, order_id=None, priority='medium'):
    """
    Creates a new inquiry ticket and performs automated triage.
    """
    ticket = InquiryTicket(
        ticket_ref=generate_ticket_ref(),
        customer_id=customer_id,
        order_id=order_id,
        subject=subject,
        description=description,
        priority=priority,
        status='open'
    )
    
    # ── Automated Triage Logic ─────────────────────────────────────────────
    # If the ticket is linked to an order, we identify the primary seller 
    # and "soft-assign" or flag it for their dashboard.
    if order_id:
        # Find first seller in the order (assuming single-vendor or primary vendor focus)
        item = OrderItem.query.filter_by(order_id=order_id).first()
        if item and item.product:
            ticket.assigned_to = item.product.seller_id
            
    db.session.add(ticket)
    try:
        db.session.commit()
        return ticket
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None

def add_reply(ticket_id, author_id, body, is_internal=False):
    """
    Adds a reply to a ticket and updates ticket state.
    """
    ticket = InquiryTicket.query.get(ticket_id)
    if not ticket:
        return None, "Ticket not found."

    reply = InquiryReply(
        ticket_id=ticket_id,
        author_id=author_id,
        body=body,
        is_internal=is_internal
    )
    
    # Logic: If seller/admin replies, set status to in_progress
    from eacis.models.user import User
    author = User.query.get(author_id)
    if author and author.role in ['seller', 'admin']:
        ticket.status = 'in_progress'
    else:
        # If customer replies, set status back to open to flag for attention
        ticket.status = 'open'
        
    db.session.add(reply)
    db.session.commit()
    return reply, "Reply added successfully."

def resolve_ticket(ticket_id, resolver_id):
    """
    Marks a ticket as resolved.
    """
    ticket = InquiryTicket.query.get(ticket_id)
    if not ticket:
        return False, "Ticket not found."
    
    ticket.status = 'resolved'
    ticket.resolved_at = datetime.utcnow()
    db.session.commit()
    return True, "Ticket resolved."
