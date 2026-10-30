"""merge heads: 20260415_merge_heads, 20260418_add_review_columns, 20260420_add_address_fields

Revision ID: 20261030_merge_all_heads
Revises: 20260415_merge_heads, 20260418_add_review_columns, 20260420_add_address_fields
Create Date: 2026-10-30 20:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20261030_merge_all_heads'
down_revision = (
    '20260415_merge_heads',
    '20260418_add_review_columns',
    '20260420_add_address_fields',
)
branch_labels = None
depends_on = None


def upgrade():
    # empty merge revision to unify parallel heads
    pass


def downgrade():
    # downgrade not supported for merge-only revision
    pass
