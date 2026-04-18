"""add return_requests.updated_at

Revision ID: 20260416_add_return_updated_at
Revises: 20260416_add_product_images
Create Date: 2026-04-16 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260416_add_return_updated_at'
down_revision = '20260416_add_product_images'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('return_requests', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('return_requests', 'updated_at')

