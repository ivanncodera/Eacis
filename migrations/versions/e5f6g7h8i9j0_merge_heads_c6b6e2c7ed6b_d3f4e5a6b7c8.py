"""merge heads: c6b6e2c7ed6b, d3f4e5a6b7c8

Revision ID: e5f6g7h8i9j0
Revises: c6b6e2c7ed6b, d3f4e5a6b7c8
Create Date: 2026-04-14 09:20:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = ('c6b6e2c7ed6b', 'd3f4e5a6b7c8')
branch_labels = None
depends_on = None


def upgrade():
    # This is an empty merge revision that unifies parallel heads.
    pass


def downgrade():
    # Downgrade not supported for merge-only revision.
    pass
