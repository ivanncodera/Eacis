"""add reviews and product_stars tables

Revision ID: 20260417_add_reviews_and_product_stars
Revises: 20260416_add_return_updated_at
Create Date: 2026-04-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260417_add_reviews_and_product_stars'
down_revision = '20260416_add_return_updated_at'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.SmallInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('is_approved', sa.Boolean(), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('reviewer_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'user_id', name='uix_product_user_review'),
    )
    op.create_index('ix_reviews_product', 'reviews', ['product_id'])

    op.create_table(
        'product_stars',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'user_id', name='uix_product_user_star'),
    )
    op.create_index('ix_product_stars_product', 'product_stars', ['product_id'])


def downgrade():
    op.drop_index('ix_product_stars_product', table_name='product_stars')
    op.drop_table('product_stars')
    op.drop_index('ix_reviews_product', table_name='reviews')
    op.drop_table('reviews')
