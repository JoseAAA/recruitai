# scripts/start.ps1 — Arranque inteligente de RecruitAI (Windows / PowerShell)
#
# Lee LLM_PROVIDER del .env y decide:
#   - ollama  → activa el profile local-llm (levanta Ollama en GPU)
#   - groq    → no levanta Ollama (cloud), valida GROQ_API_KEY
#   - gemini  → no levanta Ollama (cloud), valida GEMINI_API_KEY
#   - openai  → no levanta Ollama (cloud), valida OPENAI_API_KEY
#
# Uso:
#   .\scripts\start.ps1            → up -d (modo default del .env)
#   .\scripts\start.ps1 down       → docker compose down
#   .\scripts\start.ps1 restart    → down + up -d
#   .\scripts\start.ps1 logs       → follow logs del backend

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "restart", "logs", "status")]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# ── Cargar .env ─────────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] No se encontró .env. Copia .env.example y configúralo:" -ForegroundColor Red
    Write-Host "        cp .env.example .env" -ForegroundColor Yellow
    exit 1
}

$envVars = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
        $key = $Matches[1]
        $value = $Matches[2].Trim('"').Trim("'")
        $envVars[$key] = $value
    }
}

$provider = ($envVars["LLM_PROVIDER"] ?? "ollama").ToLower()

# ── Acciones simples sin lógica de provider ──────────────────────────────────
if ($Action -eq "down") {
    Write-Host "Bajando todos los servicios..." -ForegroundColor Cyan
    docker compose --profile local-llm down
    exit $LASTEXITCODE
}

if ($Action -eq "logs") {
    docker logs recruitai-backend -f
    exit $LASTEXITCODE
}

if ($Action -eq "status") {
    docker compose --profile local-llm ps
    exit $LASTEXITCODE
}

# ── Validación de API keys según provider ───────────────────────────────────
$cloudProviders = @{
    "groq"   = "GROQ_API_KEY"
    "gemini" = "GEMINI_API_KEY"
    "openai" = "OPENAI_API_KEY"
}

if ($cloudProviders.ContainsKey($provider)) {
    $keyName = $cloudProviders[$provider]
    $keyValue = $envVars[$keyName]
    if ([string]::IsNullOrWhiteSpace($keyValue)) {
        Write-Host "[ERROR] LLM_PROVIDER=$provider pero $keyName no está en .env" -ForegroundColor Red
        Write-Host "" -ForegroundColor Red
        Write-Host "Opciones:" -ForegroundColor Yellow
        Write-Host "  1. Obtener la API key y agregarla al .env:"
        switch ($provider) {
            "groq"   { Write-Host "     https://console.groq.com (free tier disponible)" -ForegroundColor Cyan }
            "gemini" { Write-Host "     https://aistudio.google.com/apikey (free tier 1.5k req/día)" -ForegroundColor Cyan }
            "openai" { Write-Host "     https://platform.openai.com/api-keys" -ForegroundColor Cyan }
        }
        Write-Host "  2. Cambiar a Ollama local (gratis, on-prem):"
        Write-Host "     LLM_PROVIDER=ollama" -ForegroundColor Cyan
        exit 1
    }
}
elseif ($provider -ne "ollama") {
    Write-Host "[ERROR] LLM_PROVIDER='$provider' no es válido." -ForegroundColor Red
    Write-Host "        Opciones: ollama, groq, gemini, openai" -ForegroundColor Yellow
    exit 1
}

# ── Decidir profile y mostrar resumen ──────────────────────────────────────
if ($provider -eq "ollama") {
    $profileArg = @("--profile", "local-llm")
    $modeLabel = "🦙 Ollama LOCAL (datos nunca salen, ~3 GB RAM, usa GPU)"
    $piiStatus = "PII masking: OFF (no necesario en local)"
}
else {
    $profileArg = @()
    $modeLabel = "☁️  $($provider.ToUpper()) CLOUD (Ollama apagado, libera RAM/GPU)"
    $piiStatus = "PII masking: ON (auto, datos van fuera)"

    # Si Ollama estaba corriendo, lo paramos para liberar recursos
    $ollamaRunning = docker ps --filter "name=recruitai-ollama" --format "{{.Names}}" 2>$null
    if ($ollamaRunning -eq "recruitai-ollama") {
        Write-Host "Detectado Ollama corriendo — apagándolo para liberar recursos..." -ForegroundColor Yellow
        docker compose stop ollama 2>$null | Out-Null
    }
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  RecruitAI — Modo: $modeLabel" -ForegroundColor Green
Write-Host "  $piiStatus" -ForegroundColor Gray
Write-Host "  Embeddings: SIEMPRE local (servicio TEI separado, ~600 MB RAM)" -ForegroundColor Gray
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Ejecutar ───────────────────────────────────────────────────────────────
if ($Action -eq "restart") {
    Write-Host "Reiniciando servicios..." -ForegroundColor Cyan
    & docker compose @profileArg down
}

Write-Host "Levantando servicios..." -ForegroundColor Cyan
& docker compose @profileArg up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] docker compose falló. Revisa los logs:" -ForegroundColor Red
    Write-Host "        docker compose logs --tail 50" -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "✓ Servicios levantados" -ForegroundColor Green
Write-Host "  ➜ App:       http://localhost           (entrada principal, vía nginx)" -ForegroundColor Cyan
Write-Host "  Frontend:    http://localhost:3000       (directo, solo desarrollo)" -ForegroundColor Gray
Write-Host "  API docs:    http://localhost:8000/docs  (solo ENVIRONMENT=development)" -ForegroundColor Gray
Write-Host ""
Write-Host "Primera vez: el servicio 'embeddings' descarga ~1.2 GB (Snowflake/" -ForegroundColor Yellow
Write-Host "arctic-embed-m-v2.0). Espera ~1-2 min antes de subir CVs. Verifica con:" -ForegroundColor Yellow
Write-Host "  docker logs recruitai-embeddings -f" -ForegroundColor Cyan
if ($provider -eq "ollama") {
    Write-Host ""
    Write-Host "Modo Ollama: descarga también el modelo de generación si es la primera vez:" -ForegroundColor Yellow
    Write-Host "  docker exec recruitai-ollama ollama pull gemma3:4b" -ForegroundColor Cyan
    Write-Host "  (Ya NO necesitas 'ollama pull nomic-embed-text' — embeddings van por TEI)" -ForegroundColor Gray
}
