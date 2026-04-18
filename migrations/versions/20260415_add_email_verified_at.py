"""add email_verified_at to users

Revision ID: 20260415_add_email_verified_at
Revises: 20260415_add_otp_challenges
Create Date: 2026-04-15 18:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260415_add_email_verified_at'
down_revision = '20260415_add_otp_challenges'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'email_verified_at')
