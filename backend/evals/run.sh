#!/usr/bin/env bash
# evals/run.sh — corre la suite de evals desde el container backend.
#
# Uso típico:
#   docker exec recruitai-backend bash /app/evals/run.sh           # todo
#   docker exec recruitai-backend bash /app/evals/run.sh cv        # solo CVs
#   docker exec recruitai-backend bash /app/evals/run.sh job       # solo perfiles
#   docker exec recruitai-backend bash /app/evals/run.sh match     # solo matching
#
# La primera ejecución instala inspect-ai + rapidfuzz si no están.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# ── Instalación de dependencias de evals (solo primera vez) ────────────────
if ! python -c "import inspect_ai" 2>/dev/null; then
    echo "→ Instalando dependencias de evals (inspect-ai, rapidfuzz)..."
    pip install --quiet -r requirements-evals.txt
fi

# ── Selección de qué correr ────────────────────────────────────────────────
TARGET="${1:-all}"
LOG_DIR="${LOG_DIR:-./evals/.logs}"
mkdir -p "$LOG_DIR"

run_task() {
    local task_file=$1
    local label=$2
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Evaluando: $label"
    echo "═══════════════════════════════════════════════════════════════"
    inspect eval "$task_file" --log-dir "$LOG_DIR" "${@:3}"
}

case "$TARGET" in
    cv)
        run_task evals/tasks/cv_extraction.py "Extracción de CVs"
        ;;
    job)
        run_task evals/tasks/job_profile_extraction.py "Extracción de Perfiles de Puesto"
        ;;
    match)
        run_task evals/tasks/candidate_matching.py "Matching Candidato-Vacante"
        ;;
    all)
        run_task evals/tasks/cv_extraction.py "Extracción de CVs"
        run_task evals/tasks/job_profile_extraction.py "Extracción de Perfiles de Puesto"
        run_task evals/tasks/candidate_matching.py "Matching Candidato-Vacante"
        ;;
    *)
        echo "Uso: $0 [cv|job|match|all]"
        exit 1
        ;;
esac

echo ""
echo "✓ Logs guardados en: $LOG_DIR"
echo "  Ver con: inspect view --log-dir $LOG_DIR"
