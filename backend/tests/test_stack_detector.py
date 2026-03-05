"""Tests for the stack detection algorithm."""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import PRStack, PRStackMembership, PullRequest, TrackedRepo
from src.services.stack_detector import detect_stacks


def _make_pr(
    repo_id: int,
    number: int,
    head_ref: str,
    base_ref: str,
    **kwargs,
) -> PullRequest:
    """Helper to create a PullRequest with sensible defaults."""
    now = datetime.now(UTC)
    return PullRequest(
        repo_id=repo_id,
        number=number,
        title=f"PR #{number}",
        state="open",
        draft=False,
        head_ref=head_ref,
        base_ref=base_ref,
        author="testuser",
        additions=10,
        deletions=5,
        changed_files=2,
        html_url=f"https://github.com/org/repo/pull/{number}",
        created_at=now,
        updated_at=now,
        last_synced_at=now,
        **kwargs,
    )


@pytest_asyncio.fixture
async def repo(db_session: AsyncSession) -> TrackedRepo:
    """Create a tracked repo in the test DB."""
    repo = TrackedRepo(
        owner="org",
        name="repo",
        full_name="org/repo",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()
    return repo


@pytest.mark.asyncio
async def test_no_prs_returns_empty(db_session: AsyncSession, repo: TrackedRepo):
    """No open PRs → no stacks."""
    stacks = await detect_stacks(db_session, repo.id)
    assert stacks == []


@pytest.mark.asyncio
async def test_standalone_prs_no_stack(db_session: AsyncSession, repo: TrackedRepo):
    """PRs that all target main with no chaining → no stacks."""
    db_session.add(_make_pr(repo.id, 1, "feature-a", "main"))
    db_session.add(_make_pr(repo.id, 2, "feature-b", "main"))
    await db_session.flush()

    stacks = await detect_stacks(db_session, repo.id)
    assert stacks == []


@pytest.mark.asyncio
async def test_linear_chain(db_session: AsyncSession, repo: TrackedRepo):
    """main ← PR1 ← PR2 ← PR3 should produce one stack with 3 members."""
    db_session.add(_make_pr(repo.id, 1, "branch-1", "main"))
    db_session.add(_make_pr(repo.id, 2, "branch-2", "branch-1"))
    db_session.add(_make_pr(repo.id, 3, "branch-3", "branch-2"))
    await db_session.flush()

    stacks = await detect_stacks(db_session, repo.id)
    assert len(stacks) == 1

    stack = stacks[0]
    assert stack.name == "Stack: branch-1"

    memberships = (
        await db_session.execute(
            select(PRStackMembership)
            .where(PRStackMembership.stack_id == stack.id)
            .order_by(PRStackMembership.position)
        )
    ).scalars().all()

    assert len(memberships) == 3
    assert memberships[0].position == 0
    assert memberships[0].parent_pr_id is None  # root has no parent
    assert memberships[1].position == 1
    assert memberships[1].parent_pr_id == memberships[0].pull_request_id
    assert memberships[2].position == 2
    assert memberships[2].parent_pr_id == memberships[1].pull_request_id


@pytest.mark.asyncio
async def test_fan_out(db_session: AsyncSession, repo: TrackedRepo):
    """main ← PR1 with PR2 and PR3 both based on PR1 (fan-out)."""
    db_session.add(_make_pr(repo.id, 1, "base-branch", "main"))
    db_session.add(_make_pr(repo.id, 2, "child-a", "base-branch"))
    db_session.add(_make_pr(repo.id, 3, "child-b", "base-branch"))
    await db_session.flush()

    stacks = await detect_stacks(db_session, repo.id)
    assert len(stacks) == 1

    memberships = (
        await db_session.execute(
            select(PRStackMembership)
            .where(PRStackMembership.stack_id == stacks[0].id)
            .order_by(PRStackMembership.position)
        )
    ).scalars().all()

    # Root + 2 children = 3 members
    assert len(memberships) == 3
    # Both children should have the root as parent
    child_parents = {m.parent_pr_id for m in memberships if m.parent_pr_id is not None}
    assert len(child_parents) == 1  # both point to same parent


@pytest.mark.asyncio
async def test_two_independent_stacks(db_session: AsyncSession, repo: TrackedRepo):
    """Two independent chains should produce two separate stacks."""
    # Stack A: main ← 1 ← 2
    db_session.add(_make_pr(repo.id, 1, "stack-a-1", "main"))
    db_session.add(_make_pr(repo.id, 2, "stack-a-2", "stack-a-1"))
    # Stack B: main ← 3 ← 4
    db_session.add(_make_pr(repo.id, 3, "stack-b-1", "main"))
    db_session.add(_make_pr(repo.id, 4, "stack-b-2", "stack-b-1"))
    await db_session.flush()

    stacks = await detect_stacks(db_session, repo.id)
    assert len(stacks) == 2

    names = {s.name for s in stacks}
    assert "Stack: stack-a-1" in names
    assert "Stack: stack-b-1" in names


@pytest.mark.asyncio
async def test_single_child_is_a_stack(db_session: AsyncSession, repo: TrackedRepo):
    """main ← PR1 ← PR2 (just two PRs) is still a valid stack."""
    db_session.add(_make_pr(repo.id, 1, "parent", "main"))
    db_session.add(_make_pr(repo.id, 2, "child", "parent"))
    await db_session.flush()

    stacks = await detect_stacks(db_session, repo.id)
    assert len(stacks) == 1
    assert len(
        (
            await db_session.execute(
                select(PRStackMembership).where(
                    PRStackMembership.stack_id == stacks[0].id
                )
            )
        ).scalars().all()
    ) == 2


@pytest.mark.asyncio
async def test_redetection_clears_old_stacks(
    db_session: AsyncSession, repo: TrackedRepo
):
    """Running detect_stacks again should replace previous stacks."""
    db_session.add(_make_pr(repo.id, 1, "a", "main"))
    db_session.add(_make_pr(repo.id, 2, "b", "a"))
    await db_session.flush()

    stacks_v1 = await detect_stacks(db_session, repo.id)
    assert len(stacks_v1) == 1

    # Run again — should still produce exactly one stack
    stacks_v2 = await detect_stacks(db_session, repo.id)
    assert len(stacks_v2) == 1
    assert stacks_v2[0].name == stacks_v1[0].name  # same structure detected


@pytest.mark.asyncio
async def test_nonexistent_repo_returns_empty(db_session: AsyncSession):
    """Passing a repo_id that doesn't exist → empty list, no crash."""
    stacks = await detect_stacks(db_session, 99999)
    assert stacks == []
