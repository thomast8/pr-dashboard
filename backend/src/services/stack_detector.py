"""Detect PR stacks by analyzing base_ref/head_ref relationships."""

from collections import defaultdict, deque
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import PRStack, PRStackMembership, PullRequest, TrackedRepo


async def detect_stacks(session: AsyncSession, repo_id: int) -> list[PRStack]:
    """Detect PR stacks for a repo and persist them.

    Algorithm:
    1. Build a map: head_ref → PR for all open PRs
    2. For each PR, if base_ref matches another PR's head_ref → parent-child edge
    3. BFS from roots (PRs targeting default branch) to build chains
    4. Fan-outs (multiple PRs sharing same base_ref) stored as tree branches
    """
    repo = await session.get(TrackedRepo, repo_id)
    if not repo:
        return []

    # Get all open PRs for this repo
    result = await session.execute(
        select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "open",
        )
    )
    prs = list(result.scalars().all())

    if not prs:
        return []

    # Build lookup: head_ref → PR
    head_to_pr: dict[str, PullRequest] = {}
    for pr in prs:
        head_to_pr[pr.head_ref] = pr

    # Build adjacency: parent PR → list of child PRs
    # A child PR's base_ref == parent PR's head_ref
    children: dict[int, list[PullRequest]] = defaultdict(list)
    has_parent: set[int] = set()

    for pr in prs:
        parent = head_to_pr.get(pr.base_ref)
        if parent and parent.id != pr.id:
            children[parent.id].append(pr)
            has_parent.add(pr.id)

    # Root PRs: those that have children but no parent in the stack
    # (i.e., they target the default branch or a branch not owned by another open PR)
    roots: list[PullRequest] = []
    for pr in prs:
        if pr.id not in has_parent and pr.id in children:
            roots.append(pr)

    # Also detect standalone chains where a PR is ONLY a child (leaf of stack)
    # but we need to include single-depth stacks too
    # Re-check: any PR with children is a potential root if it's not itself a child
    # Any PR that is a child but has no children is a leaf — handled via BFS

    if not roots:
        return []

    # Clear existing stacks for this repo
    await session.execute(
        delete(PRStackMembership).where(
            PRStackMembership.stack_id.in_(select(PRStack.id).where(PRStack.repo_id == repo_id))
        )
    )
    await session.execute(delete(PRStack).where(PRStack.repo_id == repo_id))

    now = datetime.now(UTC)
    new_stacks: list[PRStack] = []

    for root_pr in roots:
        # BFS to build the chain
        stack_prs: list[tuple[PullRequest, PullRequest | None]] = []  # (pr, parent_pr)
        queue: deque[tuple[PullRequest, PullRequest | None]] = deque()
        queue.append((root_pr, None))

        while queue:
            current, parent = queue.popleft()
            stack_prs.append((current, parent))
            for child in children.get(current.id, []):
                queue.append((child, current))

        # Only create a stack if it has >1 PR (a single PR is not a stack)
        if len(stack_prs) < 2:
            continue

        # Generate a name from the root PR's head_ref
        stack_name = f"Stack: {root_pr.head_ref}"

        stack = PRStack(
            repo_id=repo_id,
            name=stack_name,
            root_pr_id=root_pr.id,
            detected_at=now,
        )
        session.add(stack)
        await session.flush()  # Get stack.id

        for position, (pr, parent) in enumerate(stack_prs):
            membership = PRStackMembership(
                stack_id=stack.id,
                pull_request_id=pr.id,
                position=position,
                parent_pr_id=parent.id if parent else None,
            )
            session.add(membership)

        new_stacks.append(stack)
        logger.info(f"  Detected stack '{stack_name}' with {len(stack_prs)} PRs")

    await session.flush()
    return new_stacks
