"""
RecruitAI-Core Main Application
FastAPI entry point with CORS, routing, and health checks.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth_router, candidates_router, jobs_router, search_router, stats_router, notes_router, cloud_sync_router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("🚀 Starting RecruitAI-Core...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    logger.info(f"OneDrive OAuth: {'configured' if settings.ONEDRIVE_CLIENT_ID else 'not configured'}")
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:80",
        "http://localhost",
    ],
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
app.include_router(cloud_sync_router)  # Already has /api/cloud prefix


# ============ Exception Handlers ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
