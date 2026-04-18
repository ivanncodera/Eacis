"""seller registration docs

Revision ID: c31b9fd721aa
Revises: 9f2d4ab7e4c1
Create Date: 2026-04-14 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c31b9fd721aa'
down_revision = '9f2d4ab7e4c1'
branch_labels = None
depends_on = None


def upgrade():
    # Guard against duplicate-column errors when branches added these fields separately.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('users')] if 'users' in inspector.get_table_names() else []

    if 'business_name' not in existing_cols:
        op.add_column('users', sa.Column('business_name', sa.String(length=255), nullable=True))
    if 'business_permit_path' not in existing_cols:
        op.add_column('users', sa.Column('business_permit_path', sa.String(length=500), nullable=True))
    if 'barangay_permit_path' not in existing_cols:
        op.add_column('users', sa.Column('barangay_permit_path', sa.String(length=500), nullable=True))
    if 'mayors_permit_path' not in existing_cols:
        op.add_column('users', sa.Column('mayors_permit_path', sa.String(length=500), nullable=True))
    if 'seller_verification_status' not in existing_cols:
        op.add_column('users', sa.Column('seller_verification_status', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('users', 'seller_verification_status')
    op.drop_column('users', 'mayors_permit_path')
    op.drop_column('users', 'barangay_permit_path')
    op.drop_column('users', 'business_permit_path')
    op.drop_column('users', 'business_name')
