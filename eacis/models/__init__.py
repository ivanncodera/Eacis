try:
    from eacis.extensions import db
except Exception:
    try:
        from ..extensions import db
    except Exception:
        from extensions import db
from .address import Address
from .user import User
from .product import Product
from .order import Order, OrderItem
from .voucher import Voucher
from .voucher_usage import VoucherUsageLog
from .return_request import ReturnRequest
from .return_abuse import ReturnAbuseLog
from .refund_transaction import RefundTransaction
from .inquiry_ticket import InquiryTicket
from .inquiry_reply import InquiryReply
from .invoice import Invoice
from .cart import Cart
from .installment import InstallmentPlan, InstallmentSchedule
from .loyalty import LoyaltyTransaction
from .audit import AuditLog
from .inventory import StockMovement
from .otp_challenge import OtpChallenge

__all__ = [
    'db', 'User', 'Product', 'Order', 'OrderItem',
    'Voucher', 'VoucherUsageLog',
    'ReturnRequest', 'ReturnAbuseLog',
    'RefundTransaction', 'InquiryTicket', 'InquiryReply',
    'Invoice', 'Cart', 'InstallmentPlan', 'InstallmentSchedule',
    'LoyaltyTransaction', 'AuditLog', 'StockMovement', 'OtpChallenge',
]
