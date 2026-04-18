"""add product_images table

Revision ID: 20260416_add_product_images
Revises: 20260415_add_addresses
Create Date: 2026-04-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260416_add_product_images'
down_revision = '20260415_add_addresses'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('position', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_product_images_product_pos', 'product_images', ['product_id', 'position'])


def downgrade():
    op.drop_index('ix_product_images_product_pos', table_name='product_images')
    op.drop_table('product_images')
