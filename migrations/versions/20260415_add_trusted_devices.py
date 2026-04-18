"""add trusted_devices table

Revision ID: 20260415_add_trusted_devices
Revises: 20260415_add_email_verified_at
Create Date: 2026-04-15 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260415_add_trusted_devices'
down_revision = '20260415_add_email_verified_at'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trusted_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('device_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )

    op.create_index('ix_trusted_devices_user_created', 'trusted_devices', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_trusted_devices_user_created', table_name='trusted_devices')
    op.drop_table('trusted_devices')
