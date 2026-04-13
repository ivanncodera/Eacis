"""plan phase1 schema extensions

Revision ID: 9f2d4ab7e4c1
Revises: c6b6e2c7ed6b
Create Date: 2026-04-14 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f2d4ab7e4c1'
down_revision = 'c6b6e2c7ed6b'
branch_labels = None
depends_on = None


inquiry_priority = sa.Enum('low', 'medium', 'high', 'urgent', name='inquiry_priority')
inquiry_status = sa.Enum('open', 'in_progress', 'resolved', 'closed', name='inquiry_status')
invoice_status = sa.Enum('issued', 'paid', 'void', name='invoice_status')
refund_status = sa.Enum('requested', 'processed', 'failed', name='refund_status')


def upgrade():
    op.add_column('users', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('middle_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('suffix', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('address_line1', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('address_line2', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('barangay', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('city_municipality', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('province', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('region', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('postal_code', sa.String(length=20), nullable=True))

    inquiry_priority.create(op.get_bind(), checkfirst=True)
    inquiry_status.create(op.get_bind(), checkfirst=True)
    invoice_status.create(op.get_bind(), checkfirst=True)
    refund_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'inquiry_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_ref', sa.String(length=30), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('priority', inquiry_priority, nullable=True),
        sa.Column('status', inquiry_status, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticket_ref'),
    )

    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_ref', sa.String(length=30), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('discount_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tax_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('shipping_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('grand_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('status', invoice_status, nullable=True),
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.Column('due_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_ref'),
    )

    op.create_table(
        'refund_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('refund_ref', sa.String(length=30), nullable=False),
        sa.Column('return_request_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', refund_status, nullable=True),
        sa.Column('method', sa.String(length=50), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['return_request_id'], ['return_requests.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refund_ref'),
    )

    op.create_index('ix_orders_customer_created_at', 'orders', ['customer_id', 'created_at'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_index('ix_products_seller_active', 'products', ['seller_id', 'is_active'])
    op.create_index('ix_returns_status_created_at', 'return_requests', ['status', 'created_at'])
    op.create_index('ix_inquiries_status_priority_created_at', 'inquiry_tickets', ['status', 'priority', 'created_at'])


def downgrade():
    op.drop_index('ix_inquiries_status_priority_created_at', table_name='inquiry_tickets')
    op.drop_index('ix_returns_status_created_at', table_name='return_requests')
    op.drop_index('ix_products_seller_active', table_name='products')
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_customer_created_at', table_name='orders')

    op.drop_table('refund_transactions')
    op.drop_table('invoices')
    op.drop_table('inquiry_tickets')

    op.drop_column('users', 'postal_code')
    op.drop_column('users', 'region')
    op.drop_column('users', 'province')
    op.drop_column('users', 'city_municipality')
    op.drop_column('users', 'barangay')
    op.drop_column('users', 'address_line2')
    op.drop_column('users', 'address_line1')
    op.drop_column('users', 'suffix')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'middle_name')
    op.drop_column('users', 'first_name')

    refund_status.drop(op.get_bind(), checkfirst=True)
    invoice_status.drop(op.get_bind(), checkfirst=True)
    inquiry_status.drop(op.get_bind(), checkfirst=True)
    inquiry_priority.drop(op.get_bind(), checkfirst=True)
