try:
    from ..app import db
except Exception:
    try:
        from eacis.extensions import db
    except Exception:
        try:
            from ..extensions import db
        except Exception:
            from extensions import db
from datetime import datetime

class InstallmentPlan(db.Model):
    __tablename__ = 'installment_plans'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    months = db.Column(db.Integer)
    monthly_amount = db.Column(db.Numeric(12,2))
    downpayment = db.Column(db.Numeric(12,2), default=0)
    total_interest = db.Column(db.Numeric(12,2), default=0)
    status = db.Column(db.Enum('active','completed','defaulted', name='installment_status'))

    order = db.relationship('Order', back_populates='installment_plan', lazy='select')
    schedules = db.relationship('InstallmentSchedule', back_populates='plan', lazy='dynamic', cascade='all, delete-orphan')

class InstallmentSchedule(db.Model):
    __tablename__ = 'installment_schedule'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('installment_plans.id'))
    due_date = db.Column(db.Date)
    amount = db.Column(db.Numeric(12,2))
    status = db.Column(db.Enum('pending','paid','past_due', name='schedule_status'))
    paid_at = db.Column(db.DateTime)
    payment_ref = db.Column(db.String(100))

    plan = db.relationship('InstallmentPlan', back_populates='schedules', lazy='select')
