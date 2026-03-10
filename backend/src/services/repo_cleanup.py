"""Shared helpers for TrackedRepo cleanup."""

from loguru import logger
from sqlalchemy import delete, func
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import RepoTracker, TrackedRepo


async def delete_orphaned_repos(session: AsyncSession) -> int:
    """Delete any TrackedRepo that has zero remaining RepoTracker rows.

    Related PullRequests and PRStacks are cascade-deleted by the database.
    Does not commit; caller controls the transaction.
    Returns the count of deleted repos.
    """
    orphan_repo_ids = (
        (
            await session.execute(
                sa_select(TrackedRepo.id)
                .outerjoin(RepoTracker, RepoTracker.repo_id == TrackedRepo.id)
                .group_by(TrackedRepo.id)
                .having(func.count(RepoTracker.id) == 0)
            )
        )
        .scalars()
        .all()
    )
    if not orphan_repo_ids:
        return 0

    await session.execute(delete(TrackedRepo).where(TrackedRepo.id.in_(orphan_repo_ids)))
    logger.info(f"Deleted {len(orphan_repo_ids)} orphaned TrackedRepo(s): {orphan_repo_ids}")
    return len(orphan_repo_ids)
