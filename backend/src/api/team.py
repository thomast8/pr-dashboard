"""API routes for team member management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import TeamMemberCreate, TeamMemberOut, TeamMemberUpdate
from src.db.engine import get_session
from src.models.tables import TeamMember

router = APIRouter(prefix="/api/team", tags=["team"])


@router.get("", response_model=list[TeamMemberOut])
async def list_team(session: AsyncSession = Depends(get_session)) -> list[TeamMemberOut]:
    """List all team members."""
    members = (
        (await session.execute(select(TeamMember).order_by(TeamMember.display_name)))
        .scalars()
        .all()
    )
    return [
        TeamMemberOut(
            id=m.id,
            display_name=m.display_name,
            github_login=m.github_login,
            email=m.email,
            is_active=m.is_active,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.post("", response_model=TeamMemberOut, status_code=201)
async def add_member(
    body: TeamMemberCreate, session: AsyncSession = Depends(get_session)
) -> TeamMemberOut:
    """Add a team member."""
    member = TeamMember(
        display_name=body.display_name,
        github_login=body.github_login,
        email=body.email,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return TeamMemberOut(
        id=member.id,
        display_name=member.display_name,
        github_login=member.github_login,
        email=member.email,
        is_active=member.is_active,
        created_at=member.created_at,
    )


@router.put("/{member_id}", response_model=TeamMemberOut)
async def update_member(
    member_id: int,
    body: TeamMemberUpdate,
    session: AsyncSession = Depends(get_session),
) -> TeamMemberOut:
    """Update a team member."""
    member = await session.get(TeamMember, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    await session.commit()
    await session.refresh(member)
    return TeamMemberOut(
        id=member.id,
        display_name=member.display_name,
        github_login=member.github_login,
        email=member.email,
        is_active=member.is_active,
        created_at=member.created_at,
    )


@router.delete("/{member_id}", status_code=204)
async def deactivate_member(member_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """Deactivate a team member (soft-delete)."""
    member = await session.get(TeamMember, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    member.is_active = False
    await session.commit()
