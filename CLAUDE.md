# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the full stack (development)
```bash
docker compose up -d           # Start all services
docker compose down            # Stop all services
docker restart recruitai-frontend   # Reload frontend after code changes (hot reload doesn't detect host changes on Windows)
docker restart recruitai-backend    # Reload backend after code changes
docker logs recruitai-frontend -f   # Follow frontend logs
docker logs recruitai-backend -f    # Follow backend logs
```

### Backend (outside Docker, for isolated testing)
```bash
cd backend
pip install -r requirements.txt
python -m spacy download es_core_news_sm   # NLP model for PII detection
uvicorn app.main:app --reload --port 8000
pytest                                     # Run all tests
pytest tests/test_foo.py::test_bar -v      # Run a single test
```

### Frontend (outside Docker)
```bash
cd frontend
npm install
npm run dev        # Dev server on :3000
npm run build      # Production build (reveals real TS errors)
npm run lint
```

### Ollama models (inside Docker)
```bash
docker exec recruitai-ollama ollama pull gemma3:4b
docker exec recruitai-ollama ollama pull nomic-embed-text
docker exec recruitai-ollama ollama list
```

### DB schema changes
Schema lives in `infra/init-db.sql`. For additive changes, use idempotent DO $$ blocks (examples already in the file). The file only runs on first container creation; for existing DBs run the ALTER TABLE directly or recreate with `docker compose down -v && docker compose up -d`.

---

## Architecture

### Services (docker-compose.yml)
| Container | Role | Port |
|-----------|------|------|
| `recruitai-backend` | FastAPI + MCP server | 8000 |
| `recruitai-frontend` | Next.js 14 (App Router) | 3000 |
| `recruitai-postgres` | PostgreSQL 15 | 5432 |
| `recruitai-qdrant` | Vector DB (semantic search) | 6333 |
| `recruitai-ollama` | Local LLM inference | 11434 |
| `recruitai-minio` | S3-compatible file storage (CV files) | 9000/9001 |
| `recruitai-nginx` | Reverse proxy | 80 |

### Backend (`backend/app/`)

**Layers:**
- `api/routes/` — FastAPI routers. Each file is a separate domain: `candidates.py`, `jobs.py`, `search.py`, `auth.py`, `notes.py`, `stats.py`, `admin.py`.
- `adapters/` — External service integrations:
  - `llm_engine.py` — Unified LLM adapter (Ollama/Gemini/OpenAI). All CV extraction goes through `extract_resume()` which calls the configured provider, then applies `_normalize_extracted_resume()` (Title Case, LinkedIn URL cleanup, university name expansion).
  - `llm_providers.py` — Concrete provider implementations.
  - `embedding_service.py` — Text→vector embeddings (nomic-embed-text via Ollama).
  - `qdrant_repo.py` — Vector DB operations. Uses 4 named vectors per candidate: `experience`, `education`, `skills`, `summary`. Supports `job_id_filter` to scope searches to a specific vacancy.
  - `document_extractor.py` — PDF/DOCX → Markdown text (via pymupdf4llm).
  - `pii_masker.py` — Anonymizes PII before sending to cloud LLMs (only active when `LLM_PROVIDER != ollama`).
  - `storage.py` — MinIO file storage for raw CV files.
- `db/models.py` — SQLAlchemy ORM models (PostgreSQL).
- `domain/models.py` — Pydantic domain models (pure business logic, no DB coupling). LLM extraction output types live here (`ExtractedResume`, `ExperienciaProfesional`, etc.).
- `core/` — Config (`config.py`), JWT auth (`security.py`), async DB session (`database.py`), privacy/audit (`privacy.py`), rate limiting (`rate_limit.py`).
- `mcp_server.py` — Exposes the API as MCP tools for AI agent clients (Claude Desktop, Cursor, etc.).

**CV upload flow:**
1. `POST /api/candidates/upload` (multipart: `file` + optional `job_id` Form field)
2. `DocumentExtractor` converts PDF/DOCX → Markdown
3. `LLMEngine.extract_resume()` → structured `ExtractedResume` (Pydantic)
4. `_normalize_extracted_resume()` post-processes the LLM output
5. Embeddings generated for 4 text aspects via `EmbeddingService`
6. Candidate row + experience/education rows saved to PostgreSQL
7. Vectors + payload (including `job_id`) upserted to Qdrant

**Matching flow:**
1. `POST /api/search/match` with `{ job_id, limit }`
2. Job embedding generated from `required_skills + description`
3. Qdrant `hybrid_search` filtered by `job_id` (candidates scoped to that vacancy)
4. LLM scores each candidate against the job profile with `MATCH_MODEL`
5. Weights from `job.scoring_config` (or `DEFAULT_SCORING_CONFIG` fallback)
6. Results ranked and returned with `explanation`, `recommendation`, `missing_skills`, `bonus_skills`

**Scoring config:**
Each `JobProfileDB` has an optional `scoring_config: JSON` field with a list of `{dimension, weight, description}`. Defaults: skills 40%, experience 35%, education 25%. The frontend exposes sliders in `CreateVacancy.tsx` to customize per vacancy.

**Key DB models:**
- `CandidateDB` — has `job_id FK → job_profiles` (nullable, scopes CV to a vacancy)
- `JobProfileDB` — has `scoring_config: JSON`
- `AuditLogDB` — LPDP Perú compliance log (PostgreSQL-persisted)
- `CandidateNoteDB` — HR notes per candidate (types: `general`, `interview`, `feedback`, `status_change`)

**Valid candidate statuses:** `new`, `screening`, `shortlisted`, `interview`, `offer`, `hired`, `rejected`

**Rate limiting:** `@limit("10/minute")` decorator on upload and login endpoints (via `slowapi`). Requires `request: Request` as first parameter on decorated endpoints.

### Frontend (`frontend/src/`)

**Routing (Next.js App Router):**
- `/` → Dashboard (`components/dashboard/`)
- `/jobs` → `JobsList.tsx` — list with inline AI match modal
- `/jobs/new` → `CreateVacancy.tsx` — form with scoring config sliders
- `/jobs/[id]` → `JobDetail.tsx` — vacancy detail, candidate list, AI match results with "Preguntas IA" per card
- `/candidates` → candidates list
- `/candidates/[id]` → `CandidateDetailPage.tsx` — profile, notes, Acciones Rápidas
- `/data` → `DataIngestion.tsx` — CV upload with job selector (pre-selected if `?job_id=` in URL)

**API client:** All API calls go through `frontend/src/lib/api.ts` which exports typed functions grouped by domain: `candidatesApi`, `jobsApi`, `searchApi`, `notesApi`, `interviewApi`, `statsApi`.

**Key frontend patterns:**
- Hot reload doesn't work on Windows Docker — always `docker restart recruitai-frontend` after code changes.
- VSCode TypeScript errors (Cannot find module 'react', JSX any errors) are false positives — `node_modules` isn't on the Windows host. Check real errors with `npm run build` inside Docker.
- Interview questions generation is on match result cards (both `JobsList.tsx` and `JobDetail.tsx`), not on the candidate detail page.

### Configuration (`.env`)

Key variables (copy from `.env.example`):
```
LLM_PROVIDER=ollama            # ollama | gemini | openai
EXTRACTION_MODEL=gemma3:4b     # model for CV parsing
MATCH_MODEL=gemma3:4b          # model for candidate scoring
EMBEDDING_MODEL=nomic-embed-text
JWT_SECRET=...                 # required
ADMIN_INITIAL_PASSWORD=...     # default users created on first startup
RECRUITER_INITIAL_PASSWORD=...
PII_MASKING_ENABLED=false      # true only when using cloud providers
```

The backend mounts `./backend:/app` so code changes are live without rebuild. The frontend mounts `./frontend:/app` but requires `docker restart` on Windows due to inotify limitations.
