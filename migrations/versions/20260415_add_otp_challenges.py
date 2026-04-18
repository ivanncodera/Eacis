"""add otp_challenges table

Revision ID: 20260415_add_otp_challenges
Revises: 20260414_add_return_and_voucher_fields
Create Date: 2026-04-15 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260415_add_otp_challenges'
down_revision = '20260414_add_return_and_voucher_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'otp_challenges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('purpose', sa.String(length=50), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('sent_to', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('failure_reason', sa.String(length=100), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_otp_challenges_email_purpose_created_at', 'otp_challenges', ['email', 'purpose', 'created_at'])
    op.create_index('ix_otp_challenges_expires_at', 'otp_challenges', ['expires_at'])


def downgrade():
    op.drop_index('ix_otp_challenges_expires_at', table_name='otp_challenges')
    op.drop_index('ix_otp_challenges_email_purpose_created_at', table_name='otp_challenges')
    op.drop_table('otp_challenges')
