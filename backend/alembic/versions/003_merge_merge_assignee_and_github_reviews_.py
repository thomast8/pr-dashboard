"""merge assignee and github_reviews branches

Revision ID: 003_merge
Revises: 002_add_assignee, 002_github_reviews
Create Date: 2026-03-05 13:56:35.236365

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "003_merge"
down_revision: str | Sequence[str] | None = ("002_add_assignee", "002_github_reviews")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
