# AGENTS.md — Reglas del proyecto para agentes de IA

> Sigue el [estándar AGENTS.md](https://agents.md) (adoptado por Codex, Cursor,
> Copilot, Jules, Gemini, Windsurf, Zed, Amp). Para que Claude Code lo use,
> existe `CLAUDE.md` como symlink a este archivo.
>
> Este archivo es la **fuente única de verdad operativa** para cualquier agente
> que modifique este repositorio. Léelo entero antes de tu primera edición.

---

## 1. Qué es este proyecto

**RecruitAI** — sistema de análisis de CVs con IA para equipos de RRHH.
Sube CVs en PDF/DOCX, extrae datos con un LLM, y produce un ranking explicado
de candidatos contra una vacante.

**Diferenciador comercial:**
1. **On-premise por defecto** — los CVs nunca salen de la red del cliente.
2. **Multi-proveedor LLM con switch en `.env`** — Ollama (local), Groq, Gemini, OpenAI.
3. **100% open-source** en todo el stack operativo.

**Mercado objetivo:** PYMEs en Perú/LATAM. **Idioma del producto: español.**

---

## 2. Contexto crítico (NO discutible)

Estas decisiones están tomadas. No las re-cuestiones ni propongas alternativas
salvo que el usuario lo pida explícitamente:

- **Single-tenant on-premise.** Una instancia = una empresa. **No agregar
  `tenant_id`, no agregar multi-tenancy, no agregar facturación SaaS.**
- **No DeepSeek API.** Servidores en China, incompatible con LPDP Perú.
- **No fine-tuning propio.** Gemma3 + prompt engineering cubren el 95% de casos.
- **No app móvil.** RRHH trabaja en desktop.
- **Idioma del producto: español.** Mensajes UI, errores, prompts orientados a
  CVs hispanohablantes. El código y comentarios pueden estar en inglés.
- **Acceso compartido a vacantes y candidatos.** Todos los analistas ven todo.
  Esto es por diseño — refleja el flujo real de RRHH peruano.

---

## 3. Cumplimiento legal Perú (bloqueante)

El **Reglamento de IA peruano (DS 115-2025-PCM)** está vigente desde el
22-ene-2026 y clasifica el screening de CVs como **riesgo alto**. Obligaciones
que aplican en cada feature nueva relacionada con IA:

1. **Intervención humana obligatoria.** Ninguna decisión de aceptar/rechazar
   candidato puede ser 100% automatizada. La IA propone, el humano decide.
   → Mantén siempre visible el banner "La IA sugiere; el reclutador decide".
2. **Derecho a explicación.** El candidato puede pedir saber por qué fue
   rankeado/rechazado. Las explicaciones del LLM deben estar en lenguaje
   accesible, sin tecnicismos.
3. **Auditabilidad.** Toda acción que tome decisiones (extract_resume,
   match_candidate, status change) **debe llamar a `AuditLogger.log_access()`
   con la sesión DB**. Tabla `audit_logs` en PostgreSQL.
4. **LPDP Ley 29733.** Multas hasta S/ 550,000 (100 UIT). Cualquier cambio que
   toque PII pasa por `pii_masker.py` si va a un proveedor cloud.

**Referencias internas:** [docs/SECURITY_PROMPT_INJECTION.md](docs/SECURITY_PROMPT_INJECTION.md).

---

## 4. Arquitectura del repo

```
analisis-cv/
├── backend/                FastAPI + Python 3.11
│   ├── app/
│   │   ├── adapters/       Integraciones externas (LLM, PDF, Qdrant, S3)
│   │   ├── api/routes/     Endpoints HTTP (auth, candidates, jobs, search)
│   │   ├── core/           Config, security, rate limit, privacy
│   │   ├── db/             SQLAlchemy models y session
│   │   ├── domain/         Modelos de dominio (Pydantic)
│   │   ├── main.py         FastAPI app entrypoint
│   │   └── mcp_server.py   MCP server (fastapi-mcp)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               Next.js 14 (App Router) + TypeScript
│   ├── src/
│   │   ├── app/            Rutas (/, /jobs, /candidates, /settings, etc.)
│   │   ├── components/     Componentes React por dominio
│   │   ├── lib/            api.ts, auth-context.tsx, utils, export
│   │   └── types/
│   └── package.json
├── infra/
│   └── init-db.sql         Schema inicial Postgres (manual hasta Sprint 1)
├── docker-compose.yml      8 servicios: qdrant, postgres, ollama, minio, embeddings, backend, frontend, nginx
├── nginx.conf
├── README.md               Manual de usuario
├── DESIGN.md               Sistema visual "Slate Pro" — tokens, componentes
└── AGENTS.md               Este archivo (PLAN.md de roadmap: pendiente de crear)
```

**Servicios Docker** (todos los puertos atados a 127.0.0.1 — la única puerta
de entrada en red es nginx :80; ver §8 Seguridad):
- `qdrant` 127.0.0.1:6333 (vectores)
- `postgres` 127.0.0.1:5432 (datos)
- `minio` 127.0.0.1:9000 / :9001 (archivos)
- `embeddings` (sin puerto host) — **SIEMPRE encendido**, independiente del LLM. TEI con `Snowflake/snowflake-arctic-embed-m-v2.0` (768d, ES-EN multilingüe).
- `ollama` (sin puerto host, GPU NVIDIA) — **solo con profile `local-llm`**. Apagable cuando `LLM_PROVIDER=cloud`.
- `backend` 127.0.0.1:8000
- `frontend` 127.0.0.1:3000 (acceso directo solo para desarrollo; rewrite /api → backend)
- `nginx` :80 ← **entrada principal: http://localhost**

---

## 5. Setup inicial

```bash
git clone <repo>
cd analisis-cv
cp .env.example .env
# Edita .env: LLM_PROVIDER, JWT_SECRET, ADMIN_INITIAL_PASSWORD, RECRUITER_INITIAL_PASSWORD

# Arranque inteligente (Windows). Detecta LLM_PROVIDER y levanta lo correcto:
.\scripts\start.ps1
# Linux/macOS:
# ./scripts/start.sh

# El servicio 'embeddings' descarga el modelo automáticamente al primer arranque
# (~1.2 GB, ~1-2 min). No requiere intervención manual.

# Solo si LLM_PROVIDER=ollama: descargar el modelo de generación la primera vez
docker exec recruitai-ollama ollama pull gemma3:4b           # ~2.5 GB
# (Ya NO hace falta 'ollama pull nomic-embed-text' — embeddings van por TEI)
```

**Nunca** llamar `docker compose up` directo — siempre el script. El script
respeta el profile `local-llm` (Ollama no arranca en modo cloud, libera RAM
y GPU).

Acceso: http://localhost (nginx). Swagger en http://localhost:8000/docs (solo
en `ENVIRONMENT=development`).

**Usuarios por defecto** (creados al primer login):
- `admin@recruitai.com` / `${ADMIN_INITIAL_PASSWORD}` — rol `admin`
- `rrhh@recruitai.com` / `${RECRUITER_INITIAL_PASSWORD}` — rol `recruiter`

Los nuevos analistas se crean desde `/settings` (sección "Usuarios y Contraseñas",
visible solo para admin).

---

## 6. Comandos de desarrollo

```bash
# Arrancar / parar / reiniciar — siempre via script wrapper
.\scripts\start.ps1 up         # = .\scripts\start.ps1 (default)
.\scripts\start.ps1 restart
.\scripts\start.ps1 down
.\scripts\start.ps1 logs       # follow logs del backend
.\scripts\start.ps1 status     # ps de contenedores

# Logs específicos
docker logs recruitai-backend -f
docker logs recruitai-frontend -f

# Recargar tras editar código (Windows — hot reload no funciona por inotify)
docker restart recruitai-backend
docker restart recruitai-frontend

# Ver modelos Ollama instalados (solo si LLM_PROVIDER=ollama)
docker exec recruitai-ollama ollama list

# Reset completo (BORRA TODOS LOS DATOS — pedir confirmación al usuario)
docker compose --profile local-llm down -v
```

**Evals — medición objetiva del sistema IA** (Inspect AI, UK AISI, MIT):
```bash
# Correr toda la suite (primera vez instala dependencias)
docker exec recruitai-backend bash /app/evals/run.sh

# Solo una tarea
docker exec recruitai-backend bash /app/evals/run.sh cv      # extracción CVs
docker exec recruitai-backend bash /app/evals/run.sh job     # extracción puestos
docker exec recruitai-backend bash /app/evals/run.sh match   # matching IA

# Comparar modelos en la misma tarea
docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py \
    --model groq/llama-3.3-70b-versatile --limit 5
```
Ver `backend/evals/README.md`. **Regla**: cada bug reportado por un cliente
se convierte en un caso del dataset golden → previene regresiones para
siempre. Anonimizar datos reales antes de commitear (LPDP Perú).

**Tests de regresión deterministas** (sin LLM, corren en ~3s — SIEMPRE antes
de commitear cambios en extracción/validación):
```bash
docker exec recruitai-backend pip install -r requirements-evals.txt   # 1ª vez tras recrear el contenedor
docker exec recruitai-backend python -m pytest evals/test_extraction_robustness.py evals/test_pdf_validators.py -q
```
50 tests: 42 del pipeline de extracción (fechas, nombres, ascensos,
anti-alucinación) + 8 del validador estructural de PDFs.

**Frontend lint:**
```bash
cd frontend && npm run lint
```

**Migraciones (Alembic):**
```bash
# Primera vez en BD existente (creada por init-db.sql)
docker exec recruitai-backend alembic stamp head

# Tras editar app/db/models.py
docker exec recruitai-backend alembic revision --autogenerate -m "msg breve"
# Revisar el archivo generado en backend/alembic/versions/
docker exec recruitai-backend alembic upgrade head

# Rollback de la última migración
docker exec recruitai-backend alembic downgrade -1
```
Ver [backend/alembic/README.md](backend/alembic/README.md) para detalle.

---

## 7. Convenciones de código

### Python (backend)

- **PEP 8** con `line-length: 100` (no 88, no 120).
- **Type hints obligatorios** en toda función pública. Usa `from __future__ import annotations` si hace falta.
- **Docstrings en todas las funciones públicas.** Estilo Google.
- **Pydantic v2** para todo lo que sea entrada/salida HTTP.
- **SQLAlchemy 2.0 estilo async** con `Mapped[T]`.
- **Estructura de adapters/**: cada integración externa (LLM, Qdrant, S3) tiene
  un archivo aislado. No mezclar lógica de negocio en adapters.
- **Errores HTTP**: siempre `HTTPException(status_code=..., detail="mensaje en español")`.
- **Logging**: `logger = logging.getLogger(__name__)` por módulo. Nivel INFO
  para acciones de usuario, DEBUG para detalles internos.

### TypeScript (frontend)

- **TypeScript estricto.** No `any` salvo casos extremos comentados.
- **Next.js App Router**, "use client" solo donde se necesite.
- **Tailwind CSS** siguiendo los tokens de [DESIGN.md](DESIGN.md). No crear
  colores o tamaños fuera del sistema.
- **Componentes funcionales con hooks.** No clases.
- **Llamadas API** vía `lib/api.ts` (axios). No hacer fetch ad-hoc.
- **Estado server**: TanStack Query (ya instalado, úsalo).
- **Iconos**: Material Symbols Outlined (`<span className="material-symbols-outlined">`).
  No mezclar con Lucide aunque esté instalado para legacy.

### Mensajes y UI

- **Idioma del producto: español.**
- Tono: profesional, claro, sin jerga técnica frente a RRHH.
- Errores: mensaje en español + acción sugerida.
- Nunca usar términos como "tokens", "embeddings", "prompts" en UI de RRHH.
  Esa terminología vive en `/ops` (panel ingeniero, Sprint 5 del roadmap §14).

---

## 8. Seguridad — reglas no negociables

### Anti-prompt-injection (5 capas implementadas)

Archivo: [backend/app/adapters/llm_engine.py](backend/app/adapters/llm_engine.py).
Las 5 capas son **reales**, no docs. Si tocas el llm_engine:

1. **Layer 1 — Input patterns**: 49 regex (EN+ES) en `SUSPICIOUS_PATTERNS`.
2. **Layer 2 — Length limits**: `MAX_CV_LENGTH=50000`, `MAX_JOB=20000`.
3. **Layer 3 — Required fields**: enforcement por JSON schema.
4. **Layer 4 — Output scanning**: 8 `OUTPUT_ANOMALY_PATTERNS`.
5. **Layer 5 — Invisible Unicode**: strip U+200B–U+202E + 8 checks de
   seguridad en el PDF (texto blanco, micro-font, JS embebido, capas ocultas).

**Si agregas un patrón nuevo**, documéntalo con un comentario que explique el
ataque que mitiga. No remuevas patrones existentes sin razón documentada.

### PII y proveedores cloud

**Principio de minimización (LPDP Art. 6.4):** enviar al LLM **solo los datos
estrictamente necesarios** para la tarea. Aplica siempre, también con Ollama
local (es buena práctica, reduce tokens y simplifica el masker).

**Reglas concretas:**

- **`reason_candidate_match` NO recibe `candidate_raw_text`, `full_name`, `email`,
  `phone`, `dni`, `address` ni similares.** El LLM evalúa fit solo sobre datos
  estructurados de carrera (skills, experiencia, educación, idiomas, resumen).
  Si alguien intenta agregar un parámetro con PII, **rechazarlo en review**.
- Datos identificatorios del candidato se quedan en PostgreSQL de RecruitAI y
  se muestran al reclutador en la UI — nunca al LLM externo.
- Si `LLM_PROVIDER != "ollama"` y `PII_MASKING_ENABLED=true`, el `extract_resume`
  pasa el texto por `pii_masker.py` antes de enviarlo. Esto es **adicional** a
  la minimización, no la reemplaza.
- Detección incluye DNI peruano (8 dígitos) y RUC. No la remuevas.
- Fernet AES-256 para encriptar el mapping de PII.
- `PII_MASKING_ENABLED` se **auto-deriva** de `LLM_PROVIDER` en `core/config.py`:
  ollama → False, cloud → True. No hace falta configurarla en `.env` salvo
  override explícito.

### Credenciales

- **Nunca** comitear `.env`, claves, passwords, ni siquiera en ejemplos.
- `.env.example` solo placeholders.
- `JWT_SECRET` mínimo 32 chars.
- En `ENVIRONMENT=production`, el backend **rechaza arrancar** si detecta
  passwords por defecto. No bypasses esto.

### Dependencias

- **`axios` está fijado en `1.13.6` sin caret (`^`).** Versiones 1.14.1 y 0.30.4
  fueron comprometidas (RAT norcoreano, marzo 2026). **No actualizar `axios`
  sin verificar el changelog de seguridad de la versión objetivo.**
- Cualquier dependencia nueva: verificar mantenedor, última release, CVEs
  abiertos.

### Auditoría LPDP

Toda mutación significativa **debe llamar** `AuditLogger.log_access()` con la
DB session inyectada. **Patrón obligatorio** (Sprint 1, ya implementado):

```python
from fastapi import Depends
from app.core.privacy import AuditLogger, get_audit_logger

@router.post("/foo")
async def foo(
    current_user: UserResponse = Depends(get_current_active_user),
    audit: AuditLogger = Depends(get_audit_logger),  # ← inyección limpia
):
    # ... lógica ...
    await audit.log_access(
        user_id=str(current_user.id),
        action="resource_modified",
        resource_type="candidate",       # o "job", "user", etc.
        resource_id=str(target_id),
        ip_address=request.client.host if request.client else None,
        details={"key": "value"},        # JSON con contexto extra
    )
```

**Eventos ya cubiertos** (Sprint 1):
- `ai_match_executed` — ejecución del matching IA (DS 115 alto riesgo).
- `ai_explanation_generated_for_candidate` — derecho a explicación atendido.
- `cv_uploaded`, `cv_downloaded` — entrada/acceso a PII.
- `candidate_deleted`, `candidate_status_changed` — derechos ARCO-P y decisión final.
- `job_deleted` — cancelación masiva en cascada.
- `login_success`, `login_failed`, `login_blocked` — accesos al sistema.

**Pendientes** (Sprint 1 fase 2): notas, exports, updates de perfil, edits de
job profile. Cuando toques esos endpoints, **agrega el audit log mientras
estás ahí**.

**Nunca**: usar el viejo singleton (`get_audit_logger()` sin args como import
directo) — fue removido. Usar siempre la dependency `Depends(get_audit_logger)`.

---

## 9. Concurrencia y performance

**Estado actual:** soporta cómodamente **3 analistas concurrentes** en uso
típico de RRHH.

- Operaciones que NO usan LLM (navegar, exportar CSV, ver pipeline): ilimitadas.
- Operaciones LLM: **cola de 2 simultáneas** (`LLM_MATCH_CONCURRENCY=2`,
  `OLLAMA_NUM_PARALLEL=2`). Si los 3 analistas disparan matching al mismo
  segundo, el tercero espera ~30-60s.

**Si optimizas concurrencia:**
- No subas `OLLAMA_NUM_PARALLEL` sin medir VRAM. En RTX 3060 6GB con
  `num_ctx=16384`, cada slot consume ~1 GB de KV cache. Modelo (3.3 GB) +
  2×KV (2 GB) + embed (0.5 GB) ≈ 6.1 GB. Pasar de 2 → 3 causa OOM.
- Alternativa para alta demanda: enrutar overflow a Groq (cuando esté en `.env`).

---

## 9.5 Embeddings ≠ LLM (servicios separados)

**Patrón "separation of inference services"** (Chip Huyen, Eugene Yan,
Hugging Face, Qdrant): embeddings y generación corren en contenedores
distintos y tienen lifecycles independientes.

| Componente | Servicio Docker | Cuándo arranca | Modelo |
|---|---|---|---|
| **Embeddings** | `embeddings` (TEI HF) | **siempre** | `Snowflake/snowflake-arctic-embed-m-v2.0` (768d) |
| **LLM (generación)** | `ollama` (profile `local-llm`) o ninguno | solo si `LLM_PROVIDER=ollama`; cloud lo apaga | `gemma3:4b` (default) o cloud |

**Reglas para agentes IA:**

- **Nunca** hacer que el servicio `embeddings` dependa de `ollama` o
  viceversa. Cada uno es independiente.
- **Nunca** poner el modelo de embeddings dentro de Ollama (`ollama pull
  nomic-embed-text`). El embedding va por TEI desde dic-2024 — Ollama solo
  hace generación.
- Si necesitas cambiar el modelo de embeddings, editar solo `EMBEDDING_MODEL`
  en `.env` (default `Snowflake/snowflake-arctic-embed-m-v2.0`).
- **Cambiar a un modelo con dimensión distinta** (ej: `BAAI/bge-m3` con 1024d)
  obliga a re-indexar TODA la colección de Qdrant. Documentarlo como ADR
  antes de hacerlo.
- Si la búsqueda semántica falla, **el primer paso es ver `docker logs
  recruitai-embeddings`**, no Ollama. Son problemas distintos.

**Por qué este patrón:**

1. **Carga distinta**: embeddings se llaman 4-N veces por CV; LLM 1 vez por matching.
2. **Failure isolation**: caída de Ollama no debería romper la búsqueda y viceversa.
3. **Multi-LLM**: el cliente puede usar Groq/Gemini/OpenAI sin perder embeddings locales.
4. **Recursos**: embeddings caben en CPU (~600 MB), LLM necesita GPU (5+ GB).

## 10. Multi-proveedor LLM (una variable controla todo)

**Variable única:** `LLM_PROVIDER` en `.env`. Cambiarla ajusta a la vez:
1. Qué proveedor usa el backend (`llm_providers.get_llm_provider()`)
2. Si PII masking se activa o no (auto-derivado en `config.validate_llm_provider_and_pii`)
3. Si Ollama arranca como contenedor o no (Docker Compose profile `local-llm`)

```env
LLM_PROVIDER=ollama   # default — local, gratis, PII OFF
LLM_PROVIDER=groq     # cloud, drop-in OpenAI SDK, PII ON automático
LLM_PROVIDER=gemini   # cloud Google, free tier 1.5k req/día, PII ON
LLM_PROVIDER=openai   # cloud OpenAI, PII ON
```

**Para arrancar/cambiar/parar el sistema**, usar siempre los scripts wrapper
que leen `.env` y deciden qué levantar:

```bash
.\scripts\start.ps1 [up|down|restart|logs|status]   # Windows
./scripts/start.sh [up|down|restart|logs|status]    # Linux/macOS
```

**Fail-fast por diseño:** si `LLM_PROVIDER` es cloud y falta la API key, el
script y el backend levantan error explícito. Antes había fallback silencioso
a Ollama que causaba bugs sutiles — fue removido.

**Cómo agregar un nuevo proveedor cloud OpenAI-compatible** (Together,
Fireworks, OpenRouter, etc.):

1. Hereda de `OpenAIProvider` en `llm_providers.py` (es la clase base
   genérica). Solo sobrescribir `_provider_label`, `api_key`, `model` y
   `base_url` en `__init__`. Ver `GroqProvider` como modelo a copiar.
2. Agregar `<PROV>_API_KEY` y `<PROV>_MODEL` a `core/config.py`.
3. Agregar caso en `get_llm_provider()` con validación de API key.
4. Agregar caso en `validate_llm_provider_and_pii` (set de `valid` + dict
   `cloud_keys`).
5. Agregar caso en los scripts `scripts/start.ps1` y `scripts/start.sh`.
6. Actualizar `.env.example` y README.

**Proveedores explícitamente vetados:**
- ❌ DeepSeek: datos van a China, viola LPDP Perú.
- ⚠️ Anthropic: aceptable pero más caro; agregar solo si un cliente lo pide.

### Lecciones operativas de proveedores cloud (validadas jun-2026)

- **Cuotas free tier reales** (no las de docs viejas): Gemini free =
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier` ≈ **20 req/DÍA por
  modelo** (verificado con probe al 429); Groq free = 12k tokens/min y
  ~25-30 CVs/día. **Para pruebas en volumen, usar `LLM_PROVIDER=ollama`.**
- **Marcapasos Gemini**: `GEMINI_MIN_REQUEST_INTERVAL` (default 6.0s)
  espacia las llamadas para no provocar tormenta de 429+reintentos.
  Poner 0 con tier pagado.
- **Lifecycle Google**: los modelos Gemini mueren rápido (2.0-flash apagado
  01-jun-2026). Al cambiar `GEMINI_MODEL`, verificar contra
  `GET /v1beta/models` y https://ai.google.dev/gemini-api/docs/deprecations.
- **Modelos pensantes** (Gemini 2.5+): el "thinking" consume `maxOutputTokens`
  y trunca el JSON. `GeminiProvider` manda `thinkingBudget: 0` para modelos
  flash — no remover.
- **API key SIEMPRE por header** (`x-goog-api-key`), nunca en query string:
  las URLs aparecen en logs de error y filtran la key.
- **429/5xx agotados → `LLMRateLimitError`** (tipado). Extracción responde
  503 claro; matching marca "pendiente" SIN persistir. Nunca volver al
  fallback regex silencioso: guarda datos corruptos como si fueran buenos.
- **PII masking degradado**: Presidio NO está instalado → solo se enmascaran
  teléfono/DNI/email por regex; los NOMBRES viajan al cloud en claro.
  Para cerrar la brecha: `pip install presidio-analyzer presidio-anonymizer
  spacy && python -m spacy download es_core_news_sm` (ya previsto en
  requirements.txt como comentario).

---

## 11. Pull requests y commits

- **Commits**: estilo `feat:`, `fix:`, `chore:`, `docs:`, `refactor:` (conventional commits).
- **Mensajes**: en inglés está bien. Cuerpo del commit en español si toca lógica
  de negocio orientada a Perú.
- **Antes de PR**: corre `next lint` en frontend y (cuando exista) `pytest evals/` en backend.
- **PR description**: incluye qué cambió, por qué, y cómo se probó.
- **No comitear** `node_modules/`, `.next/`, `__pycache__/`, `uploads/`, `.venv/`, `.env`.

---

## 12. Cosas que NUNCA hacer

- ❌ Agregar `tenant_id` o multi-tenancy a la DB.
- ❌ Crear UI para "registro público" / "self-service signup". El sistema es cerrado por diseño.
- ❌ Mostrar términos técnicos (tokens, embeddings, prompts, modelos) en la UI de RRHH.
- ❌ Llamar a proveedores LLM cloud sin pasar por `pii_masker` si está habilitado.
- ❌ Pasar `candidate.raw_text`, `candidate.full_name`, `candidate.email`,
   `candidate.phone`, `candidate.linkedin` o cualquier identificatorio personal
   al LLM en el matching (`reason_candidate_match`). Esa función debe recibir
   solo competencia profesional: skills, experience, education, languages.
- ❌ Acoplar embeddings con Ollama (volver al patrón `ollama pull
   nomic-embed-text`). Embeddings van por TEI desde dic-2024; Ollama solo
   hace generación. Ver §9.5.
- ❌ Cambiar `EMBEDDING_MODEL` a un modelo con dimensión distinta (ej:
   `BAAI/bge-m3` con 1024d) sin crear ADR + plan de re-indexación de Qdrant.
- ❌ Borrar entradas de la tabla `audit_logs`. Es write-only por diseño legal.
- ❌ Skip de hooks (`--no-verify`) en commits.
- ❌ Actualizar `axios` sin verificar el changelog de seguridad.
- ❌ Cambiar el modelo Ollama default sin actualizar el README + probar con CVs reales.
- ❌ Hardcodear colores, tamaños o tipografías. Usa los tokens de [DESIGN.md](DESIGN.md).
- ❌ Crear archivos markdown sueltos (notas de planificación, decisiones). Si
   son decisiones arquitectónicas, van en `docs/adr/`. Si son operativas, en este AGENTS.md.
- ❌ Remover el `<AIDecisionBanner />` de las vistas que muestran rankings IA.
   Es requisito legal del DS 115-2025-PCM, no es decorativo.
- ❌ Cambiar el schema modificando manualmente PostgreSQL o editando
   `init-db.sql` directamente. Siempre via `alembic revision --autogenerate`.

---

## 13. Cómo trabajar con el usuario

- **Idioma de conversación: español.** El usuario es hispanohablante.
- **Nivel técnico**: bajo. Prefiere explicaciones con analogías cotidianas.
- **Pidió específicamente**:
  - Investigación profunda con fuentes — no alucinar.
  - Respuestas claras para no técnicos.
  - Que cada plan o cambio respete el diferenciador on-premise + open-source.
  - Operaciones eficientes para 3 analistas concurrentes mínimo.
- **Cuando propongas algo costoso** (consultoría, certificación, infra adicional),
  ofrece SIEMPRE una alternativa de bajo costo o gratis primero.

---

## 14. Roadmap activo

Sprints (estado a jun-2026):

1. **Sprint 1** ✅ COMPLETADO — Cumplimiento DS 115-2025-PCM + LPDP:
   audit log conectado, banner intervención humana, botón "Explicar al
   candidato", Alembic instalado.
2. **Sprint 2** ✅ COMPLETADO — Groq y Gemini como proveedores, validados
   E2E (con marcapasos de cuota, retries tipados y endurecimiento — ver §10).
3. **Sprint 3** — Dataset golden de 20 CVs + DeepEval. (Parcial: 50 tests de
   regresión deterministas en `backend/evals/test_*.py` ya corren.)
4. **Sprint 4** — Langfuse self-hosted (perfil docker opcional).
5. **Sprint 5** — UI dual `/` (RRHH) vs `/ops` (admin/ingeniero).
6. **Sprint 6** — ISO 42001 "aligned" + MODEL_CARD + DATA_CARD + SECURITY.md.
7. **Sprint 7** — Polish: caché de prompts, API v1, reranker, búsqueda híbrida.

**Pendientes para piloto** (no bloquean demo): consentimiento del candidato +
aviso de privacidad (LPDP), Presidio para enmascarar nombres en modo cloud,
rotar credenciales default antes de exponer a usuarios reales.

---

## 15. Archivos compañeros

| Archivo | Propósito | Mantenedor |
|---|---|---|
| [README.md](README.md) | Manual de usuario, instalación | José Alarcón |
| [DESIGN.md](DESIGN.md) | Sistema visual "Slate Pro" reutilizable | José Alarcón |
| `PLAN.md` | Roadmap estratégico (pendiente de crear; el roadmap vive en §14) | pendiente |
| `AGENTS.md` | Este archivo | José Alarcón |
| `CLAUDE.md` | Symlink → `AGENTS.md` | — |
| `SECURITY.md` | Política seguridad + OWASP LLM Top 10 (Sprint 6) | pendiente |
| `MODEL_CARD.md` | Ficha técnica por modelo LLM (Sprint 6) | pendiente |
| `DATA_CARD.md` | Ficha del dataset de CVs procesados (Sprint 6) | pendiente |
| `evals/README.md` | Cómo correr y agregar evals (Sprint 3) | pendiente |
| `docs/adr/*.md` | Architecture Decision Records | pendiente |

---

**Última actualización:** 2026-06-12
**Mantenedor:** José Alarcón (jose.alarcon@ibtgroup.com)
