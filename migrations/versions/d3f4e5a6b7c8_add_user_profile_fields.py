"""add user profile fields

Revision ID: d3f4e5a6b7c8
Revises: c6b6e2c7ed6b
Create Date: 2026-04-14 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f4e5a6b7c8'
down_revision = 'c6b6e2c7ed6b'
branch_labels = None
depends_on = None


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

    op.add_column('users', sa.Column('business_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('business_permit_path', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('barangay_permit_path', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('mayors_permit_path', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('seller_verification_status', sa.String(length=20), nullable=True, server_default=sa.text("'pending'")))


def downgrade():
    op.drop_column('users', 'seller_verification_status')
    op.drop_column('users', 'mayors_permit_path')
    op.drop_column('users', 'barangay_permit_path')
    op.drop_column('users', 'business_permit_path')
    op.drop_column('users', 'business_name')

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
