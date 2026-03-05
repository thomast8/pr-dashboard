# PR Dashboard

GitHub PR management dashboard for the `kyndryl-agentic-ai` organization with hierarchical zoom (org → repo → stack), live GitHub sync, and collaborative review tracking.

## Quick Start

### Backend
```bash
cd backend
cp ../.env.example .env  # Edit with your GitHub token and DB URL
uv pip install -r pyproject.toml
uv run python -m src.main
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # Starts on :5173, proxies /api to :8000
```

### Database
Requires PostgreSQL. Tables auto-create on startup via `Base.metadata.create_all`.
For migrations: `cd backend && uv run alembic upgrade head`

## Architecture

- **Backend**: FastAPI (async) + SQLAlchemy 2.0 (async) + asyncpg
- **Frontend**: React 19 + TypeScript + Vite + Zustand + @tanstack/react-query
- **Database**: PostgreSQL
- **Real-time**: Server-Sent Events (SSE)

### Key Design Decisions
- Background sync loop runs every 3 min (configurable), fetches open PRs + checks + reviews from GitHub
- Stack detection via BFS on `head_ref`/`base_ref` relationships between open PRs
- SSE broadcasts progress updates and sync completions to connected clients
- Auth: HMAC-signed session cookies (ported from PolicyAsCode-docs/server.py)

## Project Structure

```
backend/
  src/
    api/          # FastAPI route modules (repos, pulls, stacks, team, progress, auth, events)
    config/       # Pydantic settings
    db/           # SQLAlchemy engine + base
    models/       # ORM models (tables.py)
    services/     # GitHub client, sync service, stack detector, SSE events
  alembic/        # Database migrations
frontend/
  src/
    api/          # API client + types
    components/   # Shell, StatusDot, PRDetailPanel, StackGraph
    pages/        # OrgOverview, RepoView, StackDetail
    store/        # Zustand UI state
    styles/       # CSS tokens + global styles
```

## Common Commands

```bash
# Backend
cd backend && uv run python -m src.main                    # Run server
cd backend && uv run ruff format src/ && uv run ruff check src/  # Lint
cd backend && uv run alembic revision --autogenerate -m "description"  # New migration

# Frontend
cd frontend && npm run dev       # Dev server with HMR
cd frontend && npm run build     # Production build
cd frontend && npx tsc --noEmit  # Type check
```

## Environment Variables

See `.env.example` for all options. Key ones:
- `GITHUB_TOKEN` — Fine-grained PAT with read access to PRs, checks, reviews
- `DATABASE_URL` — PostgreSQL async connection string
- `DASHBOARD_PASSWORD` — Optional, enables auth (leave empty to disable)
