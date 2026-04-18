"""add return_requests and vouchers fields

Revision ID: 20260414_add_return_and_voucher_fields
Revises: c6b6e2c7ed6b
Create Date: 2026-04-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260414_add_return_and_voucher_fields'
down_revision = 'c6b6e2c7ed6b'
branch_labels = None
depends_on = None


def upgrade():
    # -- vouchers: add targeting and rules
    op.add_column('vouchers', sa.Column('target_category', sa.String(length=100), nullable=True))
    op.add_column('vouchers', sa.Column('new_customer_only', sa.Boolean(), nullable=True, server_default=sa.text('0')))
    op.add_column('vouchers', sa.Column('min_item_count', sa.Integer(), nullable=True, server_default='1'))

    # -- return_requests: add structured reason, evidence & restock fields
    reason_enum = sa.Enum('DEFECTIVE', 'WRONG_ITEM', 'NOT_AS_DESCRIBED',
                          'CHANGED_MIND', 'DAMAGED_IN_TRANSIT', 'DUPLICATE_ORDER',
                          name='return_reason_category')
    reason_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('return_requests', sa.Column('reason_category', reason_enum, nullable=True))

    op.add_column('return_requests', sa.Column('evidence_required', sa.Boolean(), nullable=True, server_default=sa.text('0')))
    op.add_column('return_requests', sa.Column('is_restockable', sa.Boolean(), nullable=True, server_default=sa.text('1')))

    item_cond_enum = sa.Enum('unopened', 'opened', 'damaged', 'missing_parts', name='return_item_condition')
    item_cond_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('return_requests', sa.Column('item_condition', item_cond_enum, nullable=True))

    op.add_column('return_requests', sa.Column('window_deadline', sa.Date(), nullable=True))


def downgrade():
    # -- return_requests
    op.drop_column('return_requests', 'window_deadline')
    op.drop_column('return_requests', 'item_condition')
    op.drop_column('return_requests', 'is_restockable')
    op.drop_column('return_requests', 'evidence_required')
    op.drop_column('return_requests', 'reason_category')
    sa.Enum(name='return_item_condition').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='return_reason_category').drop(op.get_bind(), checkfirst=True)

    # -- vouchers
    op.drop_column('vouchers', 'min_item_count')
    op.drop_column('vouchers', 'new_customer_only')
    op.drop_column('vouchers', 'target_category')
