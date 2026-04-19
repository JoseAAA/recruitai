# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the full stack (development)
```bash
docker compose up -d                        # Start all services
docker compose down                         # Stop all services
docker restart recruitai-frontend           # Reload frontend after code changes (hot reload doesn't detect host changes on Windows)
docker restart recruitai-backend            # Reload backend after code changes
docker logs recruitai-frontend -f           # Follow frontend logs
docker logs recruitai-backend -f            # Follow backend logs
```

### Backend (outside Docker, for isolated testing)
```bash
cd backend
pip install -r requirements.txt
python -m spacy download es_core_news_sm    # NLP model for PII detection
uvicorn app.main:app --reload --port 8000
pytest                                      # Run all tests
pytest tests/test_foo.py::test_bar -v       # Run a single test
```

### Frontend (outside Docker)
```bash
cd frontend
npm install
npm run dev         # Dev server on :3000
npm run build       # Production build (reveals real TS errors)
npm run lint
```

### Ollama models (inside Docker)
```bash
docker exec recruitai-ollama ollama pull gemma3:4b
docker exec recruitai-ollama ollama pull nomic-embed-text
docker exec recruitai-ollama ollama list
```

### DB schema changes
Schema lives in `infra/init-db.sql`. For additive changes, use idempotent `DO $$` blocks (examples already in the file). The file only runs on first container creation; for existing DBs run the ALTER TABLE directly or recreate with `docker compose down -v && docker compose up -d`.

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
- `api/routes/` — FastAPI routers, one file per domain: `candidates.py`, `jobs.py`, `search.py`, `auth.py`, `notes.py`, `stats.py`, `admin.py`. **All endpoints require JWT auth** via `Depends(get_current_active_user)`.
- `adapters/` — External service integrations:
  - `llm_engine.py` — Unified LLM adapter (Ollama/Gemini/OpenAI). CV extraction goes through `extract_resume()` which: (1) sanitizes input and checks for injection patterns, (2) calls the LLM provider, (3) scans output for compromise, (4) applies `_normalize_extracted_resume()` (Title Case, LinkedIn URL cleanup, university name expansion).
  - `llm_providers.py` — Concrete provider implementations.
  - `embedding_service.py` — Text→vector embeddings (nomic-embed-text via Ollama).
  - `qdrant_repo.py` — Vector DB operations. Uses 4 named vectors per candidate: `experience`, `education`, `skills`, `summary`. Supports `job_id_filter` to scope searches to a specific vacancy.
  - `document_extractor.py` — PDF/DOCX → Markdown text (via pymupdf4llm).
  - `pii_masker.py` — Anonymizes PII before sending to cloud LLMs (only active when `LLM_PROVIDER != ollama`).
  - `storage.py` — MinIO file storage for raw CV files.
- `db/models.py` — SQLAlchemy ORM models (PostgreSQL).
- `domain/models.py` — Pydantic domain models (pure business logic, no DB coupling). LLM extraction output types live here (`ExtractedResume`, `ExperienciaProfesional`, `EducacionProfesional`, etc.).
- `core/` — Config (`config.py`), JWT auth (`security.py`), async DB session (`database.py`), privacy/audit (`privacy.py`), rate limiting (`rate_limit.py`).
- `mcp_server.py` — Exposes the API as MCP tools for AI agent clients (Claude Desktop, Cursor, etc.).

**CV upload flow:**
1. `POST /api/candidates/upload` (multipart: `file` + required `job_id` Form field)
2. `job_id` is validated — upload is rejected with HTTP 400 if missing (no orphan candidates allowed)
3. File type validated by extension and magic bytes (PDF/DOCX)
4. SHA-256 hash checked for deduplication (same file + same job → return existing)
5. `DocumentExtractor` converts PDF/DOCX → Markdown
6. `LLMEngine.sanitize_input()` checks for prompt injection patterns → raises `PromptInjectionError` if found
7. `LLMEngine.extract_resume()` → structured `ExtractedResume` (Pydantic)
8. `scan_output()` scans LLM response for signs of successful injection → raises `PromptInjectionError` if found
9. `_normalize_extracted_resume()` post-processes the LLM output
10. Embeddings generated for 4 text aspects via `EmbeddingService`
11. Candidate row + experience/education rows saved to PostgreSQL
12. Vectors + payload (including `job_id`) upserted to Qdrant
13. Raw PDF/DOCX file uploaded to MinIO

**Matching flow:**
1. `POST /api/search/match` with `{ job_id, limit }`
2. Job embedding generated from `required_skills + description`
3. Qdrant `hybrid_search` filtered by `job_id` (candidates scoped to that vacancy)
4. LLM scores each candidate against the job profile with `MATCH_MODEL` (parallelized with `asyncio.gather`, max 3 concurrent)
5. Weights from `job.scoring_config` (or `DEFAULT_SCORING_CONFIG` fallback)
6. Results ranked and returned with `explanation`, `recommendation`, `missing_skills`, `bonus_skills`

**Scoring config:**
Each `JobProfileDB` has an optional `scoring_config: JSON` field with a list of `{dimension, weight, description}`. Defaults: skills 40%, experience 35%, education 25%. The frontend exposes sliders in `CreateVacancy.tsx` to customize per vacancy.

**Key DB models:**
- `CandidateDB` — has `job_id FK → job_profiles` (ON DELETE CASCADE at app layer; FK is SET NULL at DB layer but the delete endpoint explicitly deletes candidates first)
- `JobProfileDB` — has `scoring_config: JSON`
- `AuditLogDB` — LPDP Perú compliance log (PostgreSQL-persisted)
- `CandidateNoteDB` — HR notes per candidate (types: `general`, `interview`, `feedback`, `status_change`)

**Valid candidate statuses:** `new`, `screening`, `shortlisted`, `interview`, `offer`, `hired`, `rejected`

**Rate limiting:** `@limit("10/minute")` decorator on upload and login endpoints (via `slowapi`). Requires `request: Request` as first parameter on decorated endpoints.

**Education types:** `EducacionProfesional.tipo` has two valid values:
- `"educacion"` — formal academic degrees: Bachiller, Licenciatura, Ingeniería, Maestría, MBA, Doctorado
- `"certificacion"` — everything else: online courses, bootcamps, platform certifications (Coursera, AWS, Google, etc.)

The frontend (`CandidateDetailPage.tsx`) shows them in separate sections: "Formación Académica" (amber icon) and "Certificaciones" (purple icon).

### Frontend (`frontend/src/`)

**Routing (Next.js App Router):**
- `/` → Dashboard (`components/dashboard/`)
- `/jobs` → `JobsList.tsx` — list with inline AI match modal
- `/jobs/new` → `CreateVacancy.tsx` — form with scoring config sliders
- `/jobs/[id]` → `JobDetail.tsx` — vacancy detail, candidate list, AI match results with "Preguntas IA" per card
- `/candidates` → candidates list
- `/candidates/[id]` → `CandidateDetailPage.tsx` — profile (education split by tipo), notes, Acciones Rápidas
- `/data` → `DataIngestion.tsx` — CV upload with job selector (pre-selected if `?job_id=` in URL; job_id is required)

**API client:** All API calls go through `frontend/src/lib/api.ts` which exports typed functions grouped by domain: `candidatesApi`, `jobsApi`, `searchApi`, `notesApi`, `interviewApi`, `statsApi`.

**Key frontend patterns:**
- Hot reload doesn't work on Windows Docker — always `docker restart recruitai-frontend` after code changes.
- VSCode TypeScript errors (Cannot find module 'react', JSX any errors) are false positives — `node_modules` isn't on the Windows host. Check real errors with `npm run build` inside Docker.
- Interview questions generation is on match result cards (both `JobsList.tsx` and `JobDetail.tsx`), not on the candidate detail page.
- Dynamic Tailwind classes (e.g. `text-${color}-500`) are purged in production. Always use complete static class strings.

### Configuration (`.env`)

Key variables (copy from `.env.example`):
```
LLM_PROVIDER=ollama             # ollama | gemini | openai
EXTRACTION_MODEL=gemma3:4b      # model for CV parsing
MATCH_MODEL=gemma3:4b           # model for candidate scoring
EMBEDDING_MODEL=nomic-embed-text
JWT_SECRET=...                  # required — startup warns/blocks if default value
ADMIN_INITIAL_PASSWORD=...      # default users created on first startup — warns if default
RECRUITER_INITIAL_PASSWORD=...
PII_MASKING_ENABLED=false       # true only when using cloud providers
ENVIRONMENT=development         # production blocks startup with insecure defaults
```

The backend mounts `./backend:/app` so code changes are live without rebuild. The frontend mounts `./frontend:/app` but requires `docker restart` on Windows due to inotify limitations.

---

## Security

### Authentication
Every route requires `current_user: UserResponse = Depends(get_current_active_user)`. This is enforced in:
- `candidates.py` — all endpoints
- `jobs.py` — all 9 endpoints (scoring-presets, create, analyze, list, scores, get, update, delete, status)
- `notes.py` — all 3 endpoints
- `stats.py` — all 3 endpoints
- `search.py` — all endpoints
- `admin.py` — all endpoints (admin role required)

Public endpoints (no auth): `/health`, `/api/health`, `/api/auth/login`, `/api/auth/register`.

### Insecure defaults detection
`config.py` has a `model_validator` that:
- In `development`: logs a warning if `JWT_SECRET`, `ADMIN_INITIAL_PASSWORD`, or `RECRUITER_INITIAL_PASSWORD` are at their default values
- In `production` (`ENVIRONMENT=production`): raises `ValueError` and blocks startup

### Prompt injection defense (5 layers)
Documented in detail at `docs/SECURITY_PROMPT_INJECTION.md`.

Layer 1 — **Input scanning** (`sanitize_input()`): checks text against 37+ regex patterns before building the LLM prompt. Raises `PromptInjectionError` on match. This is blocking — the upload is rejected with HTTP 400.

Layer 2 — **Length limits**: CVs truncated at 50,000 chars, job descriptions at 20,000.

Layer 3 — **PII masking**: active when `PII_MASKING_ENABLED=true` (cloud providers). Replaces names/emails/phones with tokens before sending to LLM.

Layer 4 — **Output validation**: checks required fields exist in LLM JSON response.

Layer 5 — **Output scanning** (`scan_output()`): checks LLM response for signs of successful injection. Raises `PromptInjectionError` — the result is discarded, not silently passed through.

`PromptInjectionError` is explicitly re-raised in the outer `except` block so it's never swallowed by the simple-extraction fallback.

### CORS
Restricted in `main.py`:
- `allow_methods`: `GET, POST, PUT, PATCH, DELETE, OPTIONS` (not `*`)
- `allow_headers`: `Content-Type, Authorization, X-Requested-With` (not `*`)

### LLM prompt hygiene — critical rule
**Never put realistic-looking values in the LLM extraction prompt examples.** Small models (gemma3:4b) confuse example values with real CV data and copy them into the output. Use generic placeholders (`[NOMBRE DEL CV]`, `[EMAIL DEL CV]`) and institution names that don't match any real CV (`Universidad XYZ`, `Plataforma ABC`). This issue has been a recurring source of hallucinated phone numbers and emails.

### Cascade delete for candidates
When a job is deleted (`DELETE /api/jobs/{job_id}`):
1. All candidates with `job_id = <that id>` are fetched
2. Their Qdrant vectors and MinIO files are deleted
3. Candidate rows are explicitly deleted via `DELETE FROM candidates WHERE job_id = X`
4. Then the job row is deleted

Candidates with `job_id = NULL` are never cascade-deleted. The upload endpoint now rejects uploads without `job_id` to prevent orphan candidates.

---

## Known pitfalls

- **`job_id` is now required on upload** — the Form field is still `Optional[UUID]` in the function signature (for API flexibility) but the first line of the handler raises HTTP 400 if it's None.
- **`EducacionProfesional.tipo` validator** — `_normalize_tipo` converts any null/empty/unknown value to `"educacion"`. Only the exact string `"certificacion"` is preserved. This prevents silent defaults when the LLM omits the field.
- **Experience years calculation** — done in Python via `calculate_experience_years()`, not stored as a column. Uses `selectinload` to avoid N+1 queries.
- **Qdrant uses named vectors** — collection has 4 named vectors per point: `experience`, `education`, `skills`, `summary`. Queries must specify which vector(s) to use.
- **Windows hot reload** — Next.js inotify limitation. Always `docker restart recruitai-frontend` after frontend changes.
- **Real TypeScript errors** — run `docker exec recruitai-frontend npm run build` to find them. VSCode shows false positives because `node_modules` is inside the container, not on the host.
