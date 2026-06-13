"""
RecruitAI-Core Main Application
FastAPI entry point with CORS, routing, and health checks.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False

from app.api.routes import auth_router, candidates_router, jobs_router, search_router, stats_router, notes_router, admin_router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests that exceed the configured body size limit."""

    def __init__(self, app, max_body_size: int = 50 * 1024 * 1024):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return Response(
                content="Request body too large",
                status_code=413,
            )
        return await call_next(request)


async def _warmup_ollama():
    """Ensure LLM and embedding models are installed, then pre-load into GPU VRAM.

    Auto-pull: if the model configured in .env is not installed, it is pulled
    automatically before the warmup ping. Changing MATCH_MODEL or
    EXTRACTION_MODEL in .env is sufficient — no manual `ollama pull` needed.

    Runs in background so it does not block server startup.
    """
    import asyncio
    from app.core.config import settings
    from app.adapters.llm_providers import OllamaProvider

    ollama_host = getattr(settings, "OLLAMA_HOST", "http://ollama:11434")
    extraction_model = getattr(settings, "EXTRACTION_MODEL", "gemma3:4b")
    match_model = getattr(settings, "MATCH_MODEL", "gemma3:4b")
    embedding_model = getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")

    # Wait briefly for Ollama container to be fully ready
    await asyncio.sleep(5)

    # --- Step 1: auto-pull any missing models ---
    for model_name in dict.fromkeys([extraction_model, match_model, embedding_model]):
        provider = OllamaProvider(model=model_name)
        await provider.ensure_model()
        await provider.close()

    # --- Step 2: warmup ping — loads each unique model into GPU VRAM ---
    # We dedup so EXTRACTION_MODEL == MATCH_MODEL doesn't pay the load twice.
    # If they differ, both are warmed so the first /search/match doesn't pay
    # a 10-30s cold-start on top of LLM scoring time.
    import httpx
    async with httpx.AsyncClient(timeout=120.0) as client:
        for model_name in dict.fromkeys([extraction_model, match_model]):
            try:
                r = await client.post(
                    f"{ollama_host}/api/generate",
                    json={"model": model_name, "prompt": "Hola", "stream": False},
                )
                if r.status_code == 200:
                    logger.info(f"✅ Warmup: {model_name} loaded into GPU VRAM")
                else:
                    logger.warning(f"Warmup {model_name}: HTTP {r.status_code} — {r.text[:100]}")
            except Exception as e:
                logger.warning(f"Warmup {model_name} failed (will load on first request): {e}")

        try:
            r = await client.post(
                f"{ollama_host}/api/embed",
                json={"model": embedding_model, "input": "warmup"},
            )
            if r.status_code == 200:
                logger.info(f"✅ Warmup: {embedding_model} loaded into GPU VRAM")
            else:
                logger.warning(f"Warmup {embedding_model}: HTTP {r.status_code} — {r.text[:100]}")
        except Exception as e:
            logger.warning(f"Warmup {embedding_model} failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    import asyncio
    logger.info("🚀 Starting RecruitAI-Core...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    logger.info(f"PII Masking: {'enabled' if settings.PII_MASKING_ENABLED else 'disabled'}")
    # Pre-load models into GPU VRAM in background (non-blocking)
    asyncio.create_task(_warmup_ollama())
    yield
    logger.info("👋 Shutting down RecruitAI-Core...")


_is_dev = settings.ENVIRONMENT == "development"
app = FastAPI(
    title="RecruitAI-Core",
    description="AI-powered talent acquisition system with semantic search and explainable scoring",
    version="0.1.0",
    lifespan=lifespan,
    # Hide /docs, /redoc, /openapi.json in non-dev environments. They expose
    # every endpoint, schema, and example body — invaluable enumeration aid
    # for an attacker scanning the surface.
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
)

# Rate Limiting
if SLOWAPI_AVAILABLE and settings.RATE_LIMIT_ENABLED:
    from app.core.rate_limit import get_limiter
    _limiter = get_limiter()
    if _limiter:
        app.state.limiter = _limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        logger.info("Rate limiting enabled")
else:
    if not SLOWAPI_AVAILABLE:
        logger.warning("slowapi not installed — rate limiting disabled. Run: pip install slowapi")

# Body size protection
app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.MAX_UPLOAD_SIZE)

# CORS configuration
origins = (
    settings.ALLOWED_ORIGINS.split(",")
    if hasattr(settings, "ALLOWED_ORIGINS")
    else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:80",
        "http://localhost",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


# Security response headers — protect against XSS, clickjacking, MIME sniffing,
# and accidental data leak via referer. Applied uniformly to every API response.
# In production (HTTPS) we additionally emit HSTS to lock the browser into TLS.
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    # Block clickjacking — disallow our pages being framed by other sites.
    response.headers["X-Frame-Options"] = "DENY"
    # Block MIME-sniffing — prevent the browser from re-interpreting JSON as HTML/JS.
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Strip referer when navigating away — never leak internal URLs/IDs.
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Disable browser feature APIs we don't use.
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # API responses should never be cached by intermediate proxies.
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    # In production force the browser to use HTTPS for the next 6 months.
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    return response


# ============ Health Check Endpoints ============

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {
        "name": "RecruitAI-Core",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/health", tags=["Health"])
async def api_health():
    """API health check con info del proveedor activo y de los servicios.

    El frontend (hook ``useAI`` en ``lib/ai.ts``) consume este endpoint para
    pintar el indicador del header. **Por eso devuelve ``llm_provider`` con
    el valor REAL del runtime** (de ``.env``), no un placeholder estático.
    Antes esto faltaba y la UI caía al fallback ``"ollama"`` aunque el
    sistema estuviera usando Groq/Gemini/OpenAI.
    """
    from app.adapters import LLMEngine, QdrantRepository
    from app.adapters.embedding_service import EmbeddingService

    provider_name = (settings.LLM_PROVIDER or "ollama").lower()

    services = {
        "api": "healthy",
        "qdrant": "unknown",
        "embeddings": "unknown",
        provider_name: "unknown",
    }

    # Qdrant
    try:
        qdrant = QdrantRepository()
        await qdrant.get_collection_info()
        services["qdrant"] = "healthy"
    except Exception as e:
        services["qdrant"] = f"unhealthy: {str(e)[:50]}"

    # Embeddings (TEI siempre activo, independiente del LLM)
    try:
        emb = EmbeddingService()
        # Embed un texto corto como smoke test
        v = await emb.embed_text("ping")
        services["embeddings"] = "healthy" if v and len(v) > 0 else "degraded"
    except Exception as e:
        services["embeddings"] = f"unhealthy: {str(e)[:50]}"

    # Proveedor LLM activo (Ollama / Groq / Gemini / OpenAI)
    try:
        llm = LLMEngine()
        if await llm.health_check():
            services[provider_name] = "healthy"
        else:
            services[provider_name] = "unhealthy: not responding"
    except Exception as e:
        services[provider_name] = f"unhealthy: {str(e)[:50]}"

    overall = "healthy" if all(
        v == "healthy" for v in services.values()
    ) else "degraded"

    # Modelo activo según provider. ``settings.EXTRACTION_MODEL`` y
    # ``MATCH_MODEL`` se auto-sincronizan con ``OLLAMA_MODEL`` aunque se use
    # cloud (legacy del diseño anterior), por lo que NO los reportamos
    # directamente: si el provider es cloud, mostramos el modelo cloud real.
    model_by_provider = {
        "ollama": settings.OLLAMA_MODEL,
        "groq":   getattr(settings, "GROQ_MODEL", ""),
        "gemini": getattr(settings, "GEMINI_MODEL", ""),
        "openai": getattr(settings, "OPENAI_MODEL", ""),
    }
    active_model = model_by_provider.get(provider_name, "") or settings.OLLAMA_MODEL

    return JSONResponse(
        status_code=200 if overall == "healthy" else 503,
        content={
            "status": overall,
            "services": services,
            # Campos que consume el frontend (hook useAI en lib/ai.ts)
            "llm_provider": provider_name,
            "extraction_model": active_model,
            "match_model": active_model,
            "embedding_model": settings.EMBEDDING_MODEL,
        }
    )


# ============ Register Routers ============

app.include_router(auth_router, prefix="/api")
app.include_router(candidates_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(notes_router)  # Already has /api/candidates prefix
app.include_router(admin_router, prefix="/api")  # Admin-only settings management
# Cloud sync removed - using manual upload only for MVP

# ============ MCP Server (AI Agent Integration) ============
from app.mcp_server import setup_mcp
setup_mcp(app)


# ============ Exception Handlers ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
