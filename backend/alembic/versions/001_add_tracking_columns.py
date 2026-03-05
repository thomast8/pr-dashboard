"""Add tracking columns to pull_requests.

Revision ID: 001_add_tracking
Revises:
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "001_add_tracking"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pull_requests", sa.Column("head_sha", sa.String(40), nullable=True))
    op.add_column(
        "pull_requests", sa.Column("dashboard_reviewed", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "pull_requests", sa.Column("dashboard_approved", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("pull_requests", sa.Column("approved_at_sha", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("pull_requests", "approved_at_sha")
    op.drop_column("pull_requests", "dashboard_approved")
    op.drop_column("pull_requests", "dashboard_reviewed")
    op.drop_column("pull_requests", "head_sha")
