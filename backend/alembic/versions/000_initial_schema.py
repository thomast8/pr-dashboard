"""Create initial database schema.

These tables were originally created via Base.metadata.create_all() before
Alembic was introduced. This migration ensures a fresh database can be
bootstrapped entirely through `alembic upgrade head`.

Revision ID: 000_initial
Revises: (none)
Create Date: 2026-03-05
"""

import sqlalchemy as sa

from alembic import op

revision = "000_initial"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables " "WHERE table_name = :name)"
        ),
        {"name": name},
    ).scalar()


def upgrade() -> None:
    if not _table_exists("team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("github_login", sa.String(255), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    if not _table_exists("tracked_repos"):
        op.create_table(
            "tracked_repos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(512), nullable=False, unique=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("default_branch", sa.String(255), server_default="main"),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    if not _table_exists("pull_requests"):
        op.create_table(
            "pull_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "repo_id",
                sa.Integer(),
                sa.ForeignKey("tracked_repos.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(1024), nullable=False),
            sa.Column("state", sa.String(20), nullable=False),
            sa.Column("draft", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("head_ref", sa.String(255), nullable=False),
            sa.Column("base_ref", sa.String(255), nullable=False),
            sa.Column("author", sa.String(255), nullable=False),
            sa.Column("additions", sa.Integer(), server_default="0"),
            sa.Column("deletions", sa.Integer(), server_default="0"),
            sa.Column("changed_files", sa.Integer(), server_default="0"),
            sa.Column("mergeable_state", sa.String(50), nullable=True),
            sa.Column("html_url", sa.String(1024), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "last_synced_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("repo_id", "number", name="uq_repo_pr_number"),
        )

    if not _table_exists("check_runs"):
        op.create_table(
            "check_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "pull_request_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("conclusion", sa.String(50), nullable=True),
            sa.Column("details_url", sa.String(1024), nullable=True),
            sa.Column(
                "last_synced_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    if not _table_exists("reviews"):
        op.create_table(
            "reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "pull_request_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("reviewer", sa.String(255), nullable=False),
            sa.Column("state", sa.String(50), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("pr_stacks"):
        op.create_table(
            "pr_stacks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "repo_id",
                sa.Integer(),
                sa.ForeignKey("tracked_repos.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column(
                "root_pr_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id"),
                nullable=True,
            ),
            sa.Column(
                "detected_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    if not _table_exists("pr_stack_memberships"):
        op.create_table(
            "pr_stack_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "stack_id",
                sa.Integer(),
                sa.ForeignKey("pr_stacks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "pull_request_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column(
                "parent_pr_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id"),
                nullable=True,
            ),
        )

    if not _table_exists("user_progress"):
        op.create_table(
            "user_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "pull_request_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "team_member_id",
                sa.Integer(),
                sa.ForeignKey("team_members.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("reviewed", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("approved", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("pull_request_id", "team_member_id", name="uq_pr_member_progress"),
        )

    if not _table_exists("quality_snapshots"):
        op.create_table(
            "quality_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "pull_request_id",
                sa.Integer(),
                sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("pytest_passed", sa.Integer(), server_default="0"),
            sa.Column("pytest_failed", sa.Integer(), server_default="0"),
            sa.Column("pytest_errors", sa.Integer(), server_default="0"),
            sa.Column("mypy_errors", sa.Integer(), server_default="0"),
            sa.Column(
                "snapshot_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    op.drop_table("quality_snapshots")
    op.drop_table("user_progress")
    op.drop_table("pr_stack_memberships")
    op.drop_table("pr_stacks")
    op.drop_table("reviews")
    op.drop_table("check_runs")
    op.drop_table("pull_requests")
    op.drop_table("tracked_repos")
    op.drop_table("team_members")
