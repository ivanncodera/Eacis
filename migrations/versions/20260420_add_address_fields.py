"""add house_number, landmark, is_pickup, is_return to addresses

Revision ID: 20260420_add_address_fields
Revises: 20260419_add_addresses_lat_lng
Create Date: 2026-04-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260420_add_address_fields'
down_revision = '20260419_add_addresses_lat_lng'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('addresses', sa.Column('house_number', sa.String(length=128), nullable=True))
    op.add_column('addresses', sa.Column('landmark', sa.String(length=255), nullable=True))
    op.add_column('addresses', sa.Column('is_pickup', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    op.add_column('addresses', sa.Column('is_return', sa.Boolean(), nullable=True, server_default=sa.text('false')))


def downgrade():
    op.drop_column('addresses', 'is_return')
    op.drop_column('addresses', 'is_pickup')
    op.drop_column('addresses', 'landmark')
    op.drop_column('addresses', 'house_number')
