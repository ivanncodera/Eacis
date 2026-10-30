"""add lat and lng to addresses

Revision ID: 20260419_add_addresses_lat_lng
Revises: 20260415_add_addresses
Create Date: 2026-04-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260419_add_addresses_lat_lng'
down_revision = '20260415_add_addresses'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('addresses', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('addresses', sa.Column('lng', sa.Float(), nullable=True))
    op.create_index('ix_addresses_lat_lng', 'addresses', ['lat', 'lng'])


def downgrade():
    op.drop_index('ix_addresses_lat_lng', table_name='addresses')
    op.drop_column('addresses', 'lng')
    op.drop_column('addresses', 'lat')
