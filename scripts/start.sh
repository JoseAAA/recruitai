#!/usr/bin/env bash
# scripts/start.sh — Arranque inteligente de RecruitAI (Linux / macOS)
#
# Lee LLM_PROVIDER del .env y decide:
#   - ollama  → activa el profile local-llm (levanta Ollama en GPU)
#   - groq    → no levanta Ollama (cloud), valida GROQ_API_KEY
#   - gemini  → no levanta Ollama (cloud), valida GEMINI_API_KEY
#   - openai  → no levanta Ollama (cloud), valida OPENAI_API_KEY
#
# Uso:
#   ./scripts/start.sh            → up -d (modo default del .env)
#   ./scripts/start.sh down       → docker compose down
#   ./scripts/start.sh restart    → down + up -d
#   ./scripts/start.sh logs       → follow logs del backend
#   ./scripts/start.sh status     → estado de contenedores

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ACTION="${1:-up}"

# ── Colores ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

# ── Validar .env ───────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo -e "${RED}[ERROR] No se encontró .env. Copia .env.example y configúralo:${NC}"
    echo -e "${YELLOW}        cp .env.example .env${NC}"
    exit 1
fi

# Carga .env de forma segura (solo VAR=valor, ignora comentarios)
# shellcheck disable=SC2046
export $(grep -E '^[A-Z_][A-Z0-9_]*=' .env | xargs -d '\n' 2>/dev/null || grep -E '^[A-Z_][A-Z0-9_]*=' .env | xargs)

PROVIDER="${LLM_PROVIDER:-ollama}"
PROVIDER="${PROVIDER,,}"  # lowercase (bash 4+)

# ── Acciones simples ───────────────────────────────────────────────────────
case "$ACTION" in
    down)
        echo -e "${CYAN}Bajando todos los servicios...${NC}"
        docker compose --profile local-llm down
        exit $?
        ;;
    logs)
        docker logs recruitai-backend -f
        exit $?
        ;;
    status)
        docker compose --profile local-llm ps
        exit $?
        ;;
    up|restart)
        ;;
    *)
        echo -e "${RED}[ERROR] Acción desconocida: $ACTION${NC}"
        echo -e "${YELLOW}Uso: $0 [up|down|restart|logs|status]${NC}"
        exit 1
        ;;
esac

# ── Validación de API keys según provider ──────────────────────────────────
case "$PROVIDER" in
    ollama)
        ;;
    groq)
        if [ -z "${GROQ_API_KEY:-}" ]; then
            echo -e "${RED}[ERROR] LLM_PROVIDER=groq pero GROQ_API_KEY no está en .env${NC}"
            echo ""
            echo -e "${YELLOW}Opciones:${NC}"
            echo "  1. Obtener la API key (free tier disponible):"
            echo -e "     ${CYAN}https://console.groq.com${NC}"
            echo "  2. Cambiar a Ollama local (gratis, on-prem):"
            echo -e "     ${CYAN}LLM_PROVIDER=ollama${NC}"
            exit 1
        fi
        ;;
    gemini)
        if [ -z "${GEMINI_API_KEY:-}" ]; then
            echo -e "${RED}[ERROR] LLM_PROVIDER=gemini pero GEMINI_API_KEY no está en .env${NC}"
            echo ""
            echo -e "${YELLOW}Free tier 1.5k req/día:${NC}"
            echo -e "     ${CYAN}https://aistudio.google.com/apikey${NC}"
            exit 1
        fi
        ;;
    openai)
        if [ -z "${OPENAI_API_KEY:-}" ]; then
            echo -e "${RED}[ERROR] LLM_PROVIDER=openai pero OPENAI_API_KEY no está en .env${NC}"
            echo -e "${YELLOW}Obtener en: ${CYAN}https://platform.openai.com/api-keys${NC}"
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}[ERROR] LLM_PROVIDER='$PROVIDER' no es válido.${NC}"
        echo -e "${YELLOW}Opciones: ollama, groq, gemini, openai${NC}"
        exit 1
        ;;
esac

# ── Decidir profile y mostrar resumen ──────────────────────────────────────
PROFILE_ARGS=()
if [ "$PROVIDER" = "ollama" ]; then
    PROFILE_ARGS=(--profile local-llm)
    MODE_LABEL="🦙 Ollama LOCAL (datos nunca salen, ~3 GB RAM, usa GPU)"
    PII_STATUS="PII masking: OFF (no necesario en local)"
else
    MODE_LABEL="☁️  ${PROVIDER^^} CLOUD (Ollama apagado, libera RAM/GPU)"
    PII_STATUS="PII masking: ON (auto, datos van fuera)"

    # Si Ollama estaba corriendo, lo paramos
    if docker ps --filter "name=recruitai-ollama" --format "{{.Names}}" 2>/dev/null | grep -q "recruitai-ollama"; then
        echo -e "${YELLOW}Detectado Ollama corriendo — apagándolo para liberar recursos...${NC}"
        docker compose stop ollama 2>/dev/null || true
    fi
fi

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  RecruitAI — Modo: ${MODE_LABEL}${NC}"
echo -e "${GRAY}  ${PII_STATUS}${NC}"
echo -e "${GRAY}  Embeddings: SIEMPRE local (servicio TEI separado, ~600 MB RAM)${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# ── Ejecutar ───────────────────────────────────────────────────────────────
if [ "$ACTION" = "restart" ]; then
    echo -e "${CYAN}Reiniciando servicios...${NC}"
    docker compose "${PROFILE_ARGS[@]}" down
fi

echo -e "${CYAN}Levantando servicios...${NC}"
docker compose "${PROFILE_ARGS[@]}" up -d

echo ""
echo -e "${GREEN}✓ Servicios levantados${NC}"
echo -e "${CYAN}  ➜ App:       http://localhost           (entrada principal, vía nginx)${NC}"
echo -e "${GRAY}  Frontend:    http://localhost:3000       (directo, solo desarrollo)${NC}"
echo -e "${GRAY}  API docs:    http://localhost:8000/docs  (solo ENVIRONMENT=development)${NC}"
echo ""
echo -e "${YELLOW}Primera vez: el servicio 'embeddings' descarga ~1.2 GB (Snowflake/${NC}"
echo -e "${YELLOW}arctic-embed-m-v2.0). Espera ~1-2 min antes de subir CVs. Verifica con:${NC}"
echo -e "${CYAN}  docker logs recruitai-embeddings -f${NC}"
if [ "$PROVIDER" = "ollama" ]; then
    echo ""
    echo -e "${YELLOW}Modo Ollama: descarga también el modelo de generación la primera vez:${NC}"
    echo -e "${CYAN}  docker exec recruitai-ollama ollama pull gemma3:4b${NC}"
    echo -e "${GRAY}  (Ya NO necesitas 'ollama pull nomic-embed-text' — embeddings van por TEI)${NC}"
fi
