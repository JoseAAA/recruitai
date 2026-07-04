"""
MCP Server Integration for RecruitAI
Exposes FastAPI endpoints as MCP tools that any AI client
(Claude, Cursor, ChatGPT, etc.) can discover and use.

This eliminates the need for manual API configuration when
switching between AI assistants — they auto-discover available tools.

Usage:
    from app.mcp_server import setup_mcp
    setup_mcp(app)  # Call after registering all routers

The MCP server is accessible at: http://localhost:8000/mcp
"""
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_mcp(app: FastAPI) -> None:
    """
    Mount an MCP server on the FastAPI app.
    
    This auto-discovers all FastAPI routes and exposes them as MCP tools.
    AI agents connecting to /mcp can see all available endpoints,
    their schemas, and call them directly.
    
    Benefits:
    - No need to manually configure API integrations per AI client
    - Auto-generated tool descriptions from FastAPI docstrings
    - Preserves request/response schemas (Pydantic models)
    - Works with Claude Desktop, Cursor, ChatGPT, and any MCP-compatible client

    SEGURIDAD: montar el MCP auto-descubre y expone TODA la superficie del API
    (incluidos endpoints admin y sus schemas) sin autenticación. Por eso está
    apagado por defecto y solo se monta si ``MCP_ENABLED=true`` en .env. No lo
    actives en una instancia accesible desde una red no confiable.
    """
    from app.core.config import settings

    if not settings.MCP_ENABLED:
        logger.info("MCP Server deshabilitado (MCP_ENABLED=false). No se monta /mcp.")
        return

    try:
        from fastapi_mcp import FastApiMCP
        
        mcp = FastApiMCP(
            app,
            name="RecruitAI",
            description=(
                "AI-powered recruiting system. Tools for uploading CVs, "
                "managing candidates, creating job profiles, semantic search, "
                "generating interview questions, and matching candidates to jobs."
            ),
        )
        mcp.mount()
        
        logger.info("✅ MCP Server mounted at /mcp — AI agents can discover tools automatically")
        
    except ImportError:
        logger.warning(
            "⚠️ fastapi-mcp not installed. MCP endpoint disabled. "
            "Install with: pip install fastapi-mcp"
        )
    except Exception as e:
        logger.warning(f"⚠️ MCP setup failed (non-critical): {e}")
