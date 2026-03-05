"""API routes for collaborative review progress tracking."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ProgressOut, ProgressUpdate
from src.db.engine import get_session
from src.models.tables import PullRequest, TeamMember, UserProgress
from src.services.events import broadcast_event

router = APIRouter(prefix="/api/pulls", tags=["progress"])


@router.get("/{pr_id}/progress", response_model=list[ProgressOut])
async def get_progress(
    pr_id: int, session: AsyncSession = Depends(get_session)
) -> list[ProgressOut]:
    """Get all team members' progress on a PR."""
    pr = await session.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")

    results = (
        await session.execute(
            select(UserProgress, TeamMember)
            .join(TeamMember)
            .where(UserProgress.pull_request_id == pr_id)
        )
    ).all()

    return [
        ProgressOut(
            id=progress.id,
            pull_request_id=progress.pull_request_id,
            team_member_id=progress.team_member_id,
            team_member_name=member.display_name,
            reviewed=progress.reviewed,
            approved=progress.approved,
            notes=progress.notes,
            updated_at=progress.updated_at,
        )
        for progress, member in results
    ]


@router.put("/{pr_id}/progress", response_model=ProgressOut)
async def update_progress(
    pr_id: int,
    body: ProgressUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProgressOut:
    """Update a team member's progress on a PR (upsert)."""
    pr = await session.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")

    member = await session.get(TeamMember, body.team_member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    # Upsert
    result = await session.execute(
        select(UserProgress).where(
            UserProgress.pull_request_id == pr_id,
            UserProgress.team_member_id == body.team_member_id,
        )
    )
    progress = result.scalar_one_or_none()

    if progress is None:
        progress = UserProgress(
            pull_request_id=pr_id,
            team_member_id=body.team_member_id,
            reviewed=body.reviewed or False,
            approved=body.approved or False,
            notes=body.notes,
        )
        session.add(progress)
    else:
        if body.reviewed is not None:
            progress.reviewed = body.reviewed
        if body.approved is not None:
            progress.approved = body.approved
        if body.notes is not None:
            progress.notes = body.notes

    await session.commit()
    await session.refresh(progress)

    out = ProgressOut(
        id=progress.id,
        pull_request_id=progress.pull_request_id,
        team_member_id=progress.team_member_id,
        team_member_name=member.display_name,
        reviewed=progress.reviewed,
        approved=progress.approved,
        notes=progress.notes,
        updated_at=progress.updated_at,
    )

    # Broadcast progress update via SSE
    await broadcast_event(
        "progress_update",
        {
            "pr_id": pr_id,
            "team_member_id": body.team_member_id,
            "reviewed": progress.reviewed,
            "approved": progress.approved,
        },
    )

    return out
