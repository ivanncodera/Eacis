"""Merge multiple migration heads

Revision ID: 87be870cc478
Revises: c31b9fd721aa, e5f6g7h8i9j0
Create Date: 2026-04-14 06:28:13.499466

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '87be870cc478'
down_revision = ('c31b9fd721aa', 'e5f6g7h8i9j0')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
