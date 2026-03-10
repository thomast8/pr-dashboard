"""add commenters column to pull_requests

Revision ID: a66a3ecc331d
Revises: 011
Create Date: 2026-03-10 17:30:19.356890

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a66a3ecc331d"
down_revision: str | Sequence[str] | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pull_requests",
        sa.Column(
            "commenters",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("pull_requests", "commenters")
