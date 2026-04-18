"""merge heads: 87be870cc478, 20260415_add_trusted_devices

Revision ID: 20260415_merge_heads
Revises: 87be870cc478, 20260415_add_trusted_devices
Create Date: 2026-04-15 19:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20260415_merge_heads'
down_revision = ('87be870cc478', '20260415_add_trusted_devices')
branch_labels = None
depends_on = None


def upgrade():
    # empty merge revision to unify parallel heads
    pass


def downgrade():
    # downgrade not supported for merge-only revision
    pass
