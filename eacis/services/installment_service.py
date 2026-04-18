"""
Installment Service — overdue sync, eligibility checks, and payment recording.
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
    from eacis.models.installment import InstallmentPlan, InstallmentSchedule
    from eacis.models.order import Order
    from eacis.models.return_abuse import ReturnAbuseLog
    from eacis.config import Config
except Exception:
    try:
        from ..models.installment import InstallmentPlan, InstallmentSchedule
        from ..models.order import Order
        from ..models.return_abuse import ReturnAbuseLog
        from ..config import Config
    except Exception:
        from models.installment import InstallmentPlan, InstallmentSchedule
        from models.order import Order
        from models.return_abuse import ReturnAbuseLog
        from config import Config


def sync_overdue_schedules():
    """
    Find all pending schedules where due_date < today → mark past_due.
    Also mark parent plans as 'defaulted' if ALL remaining schedules are past_due.
    Lightweight — only updates rows that need it.
    """
    today = datetime.utcnow().date()
    overdue = InstallmentSchedule.query.filter(
        InstallmentSchedule.status == 'pending',
        InstallmentSchedule.due_date < today,
    ).all()

    updated_plan_ids = set()
    for schedule in overdue:
        schedule.status = 'past_due'
        updated_plan_ids.add(schedule.plan_id)

    # Check if entire plans are now defaulted
    for plan_id in updated_plan_ids:
        plan = InstallmentPlan.query.get(plan_id)
        if plan and plan.status == 'active':
            remaining = InstallmentSchedule.query.filter(
                InstallmentSchedule.plan_id == plan_id,
                InstallmentSchedule.status.in_(['pending', 'past_due']),
            ).all()
            if remaining and all(s.status == 'past_due' for s in remaining):
                plan.status = 'defaulted'

    return len(overdue)


def check_installment_eligibility(customer_id):
    """
    Returns (eligible: bool, disqualifiers: list[str]).

    Requirements:
      1. Customer has at least INSTALLMENT_MIN_COMPLETED_ORDERS delivered/paid orders
      2. No past_due InstallmentSchedule linked to any of this customer's active plans
      3. ReturnAbuseLog.is_restricted == False (account in good standing)
    """
    disqualifiers = []
    min_orders = int(getattr(Config, 'INSTALLMENT_MIN_COMPLETED_ORDERS', 1))

    # 1. Completed orders requirement
    completed = Order.query.filter(
        Order.customer_id == customer_id,
        Order.status.in_(['paid', 'delivered']),
    ).count()
    if completed < min_orders:
        disqualifiers.append(
            f'You need at least {min_orders} completed order(s) before using installment. '
            f'You currently have {completed}.'
        )

    # 2. No past-due installments
    customer_order_ids = [
        o.id for o in
        Order.query.filter_by(customer_id=customer_id).with_entities(Order.id).all()
    ]
    if customer_order_ids:
        past_due = (
            db.session.query(InstallmentSchedule.id)
            .join(InstallmentPlan, InstallmentPlan.id == InstallmentSchedule.plan_id)
            .filter(
                InstallmentPlan.order_id.in_(customer_order_ids),
                InstallmentSchedule.status == 'past_due',
            )
            .first()
        )
        if past_due:
            disqualifiers.append(
                'You have overdue installment payments. Please settle them before opening a new installment plan.'
            )

    # 3. Account not restricted (return abuse)
    abuse_log = ReturnAbuseLog.query.filter_by(customer_id=customer_id).first()
    if abuse_log and abuse_log.is_restricted:
        disqualifiers.append(
            'Your account is currently under review and cannot use installment at this time.'
        )

    eligible = len(disqualifiers) == 0
    return eligible, disqualifiers


def record_payment(schedule_id, payment_ref, actor_id=None):
    """
    Mark a single schedule row as 'paid'.
    If all rows in the plan are now paid → mark plan as 'completed'.
    """
    schedule = InstallmentSchedule.query.get(schedule_id)
    if not schedule:
        return False, 'Schedule not found.'
    if schedule.status == 'paid':
        return False, 'This schedule is already marked as paid.'

    schedule.status = 'paid'
    schedule.paid_at = datetime.utcnow()
    schedule.payment_ref = payment_ref or f'MANUAL-{datetime.utcnow().strftime("%y%m%d%H%M%S")}'

    plan = InstallmentPlan.query.get(schedule.plan_id)
    if plan:
        all_schedules = InstallmentSchedule.query.filter_by(plan_id=plan.id).all()
        if all(s.status == 'paid' for s in all_schedules):
            plan.status = 'completed'

    return True, 'Payment recorded.'


def get_plan_summary(plan_id):
    """
    Returns a dict with plan status metrics.
    """
    plan = InstallmentPlan.query.get(plan_id)
    if not plan:
        return None

    schedules = InstallmentSchedule.query.filter_by(plan_id=plan_id).order_by(InstallmentSchedule.due_date).all()
    paid = [s for s in schedules if s.status == 'paid']
    pending = [s for s in schedules if s.status in ('pending', 'past_due')]
    next_due = min(pending, key=lambda s: s.due_date) if pending else None

    return {
        'plan': plan,
        'total_schedules': len(schedules),
        'paid_count': len(paid),
        'remaining_count': len(pending),
        'total_paid': sum(float(s.amount or 0) for s in paid),
        'total_outstanding': sum(float(s.amount or 0) for s in pending),
        'next_due': next_due,
        'progress_pct': (len(paid) / len(schedules) * 100.0) if schedules else 0.0,
    }
