"""add missing review columns

Revision ID: 20260418_add_review_columns
Revises: 20260417_add_reviews_and_product_stars
Create Date: 2026-04-17 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260418_add_review_columns'
down_revision = '20260417_add_reviews_and_product_stars'
branch_labels = None
depends_on = None


def upgrade():
    # add is_anonymous if missing
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('reviews')]
    if 'is_anonymous' not in cols:
        op.add_column('reviews', sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    if 'reviewer_name' not in cols:
        op.add_column('reviews', sa.Column('reviewer_name', sa.String(length=255), nullable=True))


def downgrade():
    # remove columns if present
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('reviews')]
    if 'reviewer_name' in cols:
        op.drop_column('reviews', 'reviewer_name')
    if 'is_anonymous' in cols:
        op.drop_column('reviews', 'is_anonymous')
