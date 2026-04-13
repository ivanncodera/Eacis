try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from .user import User
from .product import Product
from .order import Order, OrderItem
from .voucher import Voucher
from .return_request import ReturnRequest
from .refund_transaction import RefundTransaction
from .inquiry_ticket import InquiryTicket
from .invoice import Invoice
from .cart import Cart
from .installment import InstallmentPlan, InstallmentSchedule
from .loyalty import LoyaltyTransaction
from .audit import AuditLog

__all__ = [
    'db', 'User', 'Product', 'Order', 'OrderItem', 'Voucher', 'ReturnRequest',
    'RefundTransaction', 'InquiryTicket', 'Invoice',
    'Cart', 'InstallmentPlan', 'InstallmentSchedule', 'LoyaltyTransaction', 'AuditLog'
]
