"""API routes for space management (multi-GitHub-source connections)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_github_user_id
from src.api.schemas import SpaceCreate, SpaceOut, SpaceUpdate
from src.db.engine import get_session
from src.models.tables import Space, TrackedRepo, User
from src.services.crypto import decrypt_token, encrypt_token
from src.services.github_client import GitHubClient

router = APIRouter(prefix="/api/spaces", tags=["spaces"])


@router.get("", response_model=list[SpaceOut])
async def list_spaces(
    session: AsyncSession = Depends(get_session),
) -> list[SpaceOut]:
    """List all spaces (token not included in response)."""
    spaces = (
        (await session.execute(select(Space).where(Space.is_active.is_(True))))
        .scalars()
        .all()
    )
    return [
        SpaceOut(
            id=s.id,
            name=s.name,
            slug=s.slug,
            space_type=s.space_type,
            base_url=s.base_url,
            is_active=s.is_active,
            has_token=bool(s.encrypted_token),
            created_at=s.created_at,
        )
        for s in spaces
    ]


@router.post("", response_model=SpaceOut, status_code=201)
async def create_space(
    body: SpaceCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SpaceOut:
    """Create a new space. Token can be a PAT or 'use_oauth' to copy from logged-in user."""
    encrypted = None
    if body.token == "use_oauth":
        user_id = get_github_user_id(request)
        if not user_id:
            raise HTTPException(
                status_code=400, detail="Not connected to GitHub"
            )
        user = await session.get(User, user_id)
        if not user or not user.encrypted_token:
            raise HTTPException(
                status_code=400, detail="No OAuth token available"
            )
        encrypted = user.encrypted_token
    elif body.token:
        encrypted = encrypt_token(body.token)

    space = Space(
        name=body.name,
        slug=body.slug,
        space_type=body.space_type,
        base_url=body.base_url or "https://api.github.com",
        encrypted_token=encrypted,
    )
    session.add(space)
    await session.commit()
    await session.refresh(space)
    logger.info(f"Created space: {space.name} ({space.slug})")

    return SpaceOut(
        id=space.id,
        name=space.name,
        slug=space.slug,
        space_type=space.space_type,
        base_url=space.base_url,
        is_active=space.is_active,
        has_token=bool(space.encrypted_token),
        created_at=space.created_at,
    )


@router.put("/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: int,
    body: SpaceUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SpaceOut:
    """Update a space."""
    space = await session.get(Space, space_id)
    if not space or not space.is_active:
        raise HTTPException(status_code=404, detail="Space not found")

    if body.name is not None:
        space.name = body.name
    if body.slug is not None:
        space.slug = body.slug
    if body.space_type is not None:
        space.space_type = body.space_type
    if body.base_url is not None:
        space.base_url = body.base_url

    if body.token is not None:
        if body.token == "use_oauth":
            user_id = get_github_user_id(request)
            if not user_id:
                raise HTTPException(
                    status_code=400, detail="Not connected to GitHub"
                )
            user = await session.get(User, user_id)
            if not user or not user.encrypted_token:
                raise HTTPException(
                    status_code=400, detail="No OAuth token available"
                )
            space.encrypted_token = user.encrypted_token
        elif body.token:
            space.encrypted_token = encrypt_token(body.token)

    await session.commit()
    await session.refresh(space)

    return SpaceOut(
        id=space.id,
        name=space.name,
        slug=space.slug,
        space_type=space.space_type,
        base_url=space.base_url,
        is_active=space.is_active,
        has_token=bool(space.encrypted_token),
        created_at=space.created_at,
    )


@router.delete("/{space_id}", status_code=204)
async def delete_space(
    space_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    """Soft-delete a space."""
    space = await session.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    space.is_active = False
    await session.commit()


@router.get("/{space_id}/available-repos")
async def list_available_repos(
    space_id: int, session: AsyncSession = Depends(get_session)
):
    """List repos in a space's org/user that are not yet tracked."""
    space = await session.get(Space, space_id)
    if not space or not space.is_active:
        raise HTTPException(status_code=404, detail="Space not found")
    if not space.encrypted_token:
        raise HTTPException(status_code=400, detail="Space has no token")

    token = decrypt_token(space.encrypted_token)
    gh = GitHubClient(token=token, base_url=space.base_url)
    try:
        if space.space_type == "org":
            repos = await gh.list_org_repos(space.slug)
        else:
            repos = await gh.list_user_repos(space.slug)
    finally:
        await gh.close()

    tracked = set(
        (await session.execute(select(TrackedRepo.full_name))).scalars().all()
    )

    return [
        {
            "name": r["name"],
            "full_name": r["full_name"],
            "description": r.get("description"),
            "private": r.get("private", False),
            "pushed_at": r.get("pushed_at"),
        }
        for r in repos
        if not r.get("archived") and r["full_name"] not in tracked
    ]


@router.post("/{space_id}/connectivity")
async def check_connectivity(
    space_id: int, session: AsyncSession = Depends(get_session)
):
    """Validate that the space token can connect to GitHub."""
    space = await session.get(Space, space_id)
    if not space or not space.is_active:
        raise HTTPException(status_code=404, detail="Space not found")
    if not space.encrypted_token:
        raise HTTPException(status_code=400, detail="Space has no token")

    token = decrypt_token(space.encrypted_token)
    gh = GitHubClient(token=token, base_url=space.base_url)
    try:
        rate = await gh.get_rate_limit()
        return {
            "ok": True,
            "rate_limit": rate.get("rate", {}).get("limit"),
            "rate_remaining": rate.get("rate", {}).get("remaining"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        await gh.close()
