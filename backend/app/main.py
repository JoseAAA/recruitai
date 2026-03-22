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
    """Pre-load LLM and embedding models into GPU VRAM on startup.

    Avoids the 20-30s cold-start delay on the first CV upload of each session.
    Runs in background so it doesn't block server startup.
    """
    import asyncio
    import httpx
    from app.core.config import settings

    ollama_host = getattr(settings, "OLLAMA_HOST", "http://ollama:11434")
    extraction_model = getattr(settings, "EXTRACTION_MODEL", "gemma3:4b")
    embedding_model = getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")

    # Wait briefly for Ollama to be fully ready
    await asyncio.sleep(5)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Pre-load extraction model — send a tiny prompt to trigger model loading
        try:
            r = await client.post(
                f"{ollama_host}/api/generate",
                json={"model": extraction_model, "prompt": "Hola", "stream": False},
            )
            if r.status_code == 200:
                logger.info(f"✅ Warmup: {extraction_model} loaded into GPU VRAM")
            else:
                logger.warning(f"Warmup {extraction_model}: HTTP {r.status_code} — {r.text[:100]}")
        except Exception as e:
            logger.warning(f"Warmup {extraction_model} failed (will load on first request): {e}")

        # Pre-load embedding model
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


app = FastAPI(
    title="RecruitAI-Core",
    description="AI-powered talent acquisition system with semantic search and explainable scoring",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
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
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    """API health check with service status."""
    from app.adapters import LLMEngine, QdrantRepository
    
    services = {
        "api": "healthy",
        "qdrant": "unknown",
        "ollama": "unknown",
    }
    
    # Check Qdrant
    try:
        qdrant = QdrantRepository()
        info = await qdrant.get_collection_info()
        services["qdrant"] = "healthy"
    except Exception as e:
        services["qdrant"] = f"unhealthy: {str(e)[:50]}"
    
    # Check Ollama
    try:
        llm = LLMEngine()
        if await llm.health_check():
            services["ollama"] = "healthy"
        else:
            services["ollama"] = "unhealthy: not responding"
    except Exception as e:
        services["ollama"] = f"unhealthy: {str(e)[:50]}"
    
    overall = "healthy" if all(
        v == "healthy" for v in services.values()
    ) else "degraded"
    
    return JSONResponse(
        status_code=200 if overall == "healthy" else 503,
        content={
            "status": overall,
            "services": services,
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
