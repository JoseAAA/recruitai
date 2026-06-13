# 🤖 RecruitAI

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/UI-Next.js%2014-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL%2015-336791.svg)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Vectores-Qdrant-DC244C.svg)](https://qdrant.tech/)
[![Docker](https://img.shields.io/badge/Infra-Docker%20Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Análisis de CVs con IA para equipos de RRHH. Subes CVs en PDF/DOCX, la IA extrae los datos y produce un **ranking explicado** de candidatos para cada vacante. Funciona **100% local** con Ollama (los datos nunca salen) o en la **nube** (Groq / Gemini / OpenAI).

---

## 📋 Contenido

- [🚀 Instalación](#-instalación)
- [🔄 Local o nube](#-local-o-nube)
- [🧰 Stack](#-stack)
- [🧱 Arquitectura](#-arquitectura)
- [📁 Estructura del proyecto](#-estructura-del-proyecto)
- [🔐 Seguridad](#-seguridad)
- [🩺 Problemas comunes](#-problemas-comunes)
- [🏭 Producción](#-producción)

---

## 🚀 Instalación

**Prerrequisitos:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) y Git. Nada más (ni Python ni Node en tu máquina).

```bash
# 1. Clonar y configurar
git clone https://github.com/JoseAAA/recruitai.git
cd recruitai
cp .env.example .env
```

```env
# 2. Editar .env (mínimo): secreto y contraseñas
JWT_SECRET=una-cadena-larga-y-aleatoria
ADMIN_INITIAL_PASSWORD=tu-password-seguro
RECRUITER_INITIAL_PASSWORD=tu-password-seguro
```

```bash
# 3. Arrancar (usa el script, NO 'docker compose up' directo)
.\scripts\start.ps1        # Windows  ·  acciones: up | down | restart | logs | status
./scripts/start.sh         # Linux / macOS
```

Accede en **[http://localhost](http://localhost)** con `admin@recruitai.com` y tu contraseña.

> La base de datos se crea y migra **sola** al arrancar. El servicio de embeddings descarga su modelo (~1.2 GB) la primera vez (~1-2 min). La primera ejecución también baja las imágenes Docker (~2-3 GB).

## 🔄 Local o nube

Una sola variable, **`LLM_PROVIDER`** en `.env`, controla todo: el proveedor, el enmascarado de datos personales y si Ollama se enciende.

| `LLM_PROVIDER` | Privacidad | Costo | Velocidad | Hardware |
|----------------|-----------|-------|-----------|----------|
| `ollama` *(default)* | 🟢 Total — datos no salen | 🟢 Gratis e ilimitado | 🟡 Según tu GPU | NVIDIA 6+ GB VRAM |
| `groq` | 🟡 Nube | 🟢 Free ~25-30 CVs/día | 🟢 Muy rápido | Cualquiera |
| `gemini` | 🟡 Nube | 🟡 Free ~20 análisis/día por modelo | 🟢 Rápido | Cualquiera |
| `openai` | 🟡 Nube | 🟡 De pago | 🟢 Rápido | Cualquiera |

**🖥️ Opción A — Local con Ollama (default):** no agregas nada al `.env`. Solo descarga el modelo la primera vez (con Ollama arriba):

```bash
docker exec recruitai-ollama ollama pull gemma3:4b   # ~2.5 GB
```

**☁️ Opción B — Nube con API key:** pon el proveedor y su key en `.env`, luego reinicia:

```env
LLM_PROVIDER=groq          # o gemini, openai
GROQ_API_KEY=gsk_...
```
```bash
.\scripts\start.ps1 restart
```

> **API keys:** [Groq](https://console.groq.com) · [Gemini](https://aistudio.google.com/apikey) · [OpenAI](https://platform.openai.com/api-keys). Si eliges nube y falta la key, el sistema **falla con un mensaje claro** (no se cae en silencio a otro modo). Modelos por defecto y opciones avanzadas: ver `.env.example`.
>
> 💡 **Para procesar muchos CVs usa Ollama** (gratis e ilimitado). Las cuotas gratuitas de la nube son para demos puntuales.

## 🧰 Stack

| Capa | Tecnología |
|------|------------|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy async · Pydantic v2 |
| **Frontend** | Next.js 14 (App Router) · TypeScript · Tailwind CSS |
| **Base de datos** | PostgreSQL 15 (incluye `audit_logs` para trazabilidad LPDP) |
| **Búsqueda semántica** | Qdrant (4 vectores por candidato) |
| **Embeddings** | TEI · `Snowflake/arctic-embed-m` (768d, multilingüe ES/EN) |
| **LLM** | Ollama (local) · o Groq / Gemini / OpenAI (nube) |
| **Archivos** | MinIO (S3-compatible) |
| **Infraestructura** | Docker Compose · Nginx |

## 🧱 Arquitectura

```
Navegador ──▶  http://localhost  (Nginx, única puerta de entrada)
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      Next.js (UI)        FastAPI (API + MCP server)
                                  │
   ┌──────────┬──────────┬────────┴───────┬───────────┬──────────────┐
   ▼          ▼          ▼                ▼           ▼              ▼
PostgreSQL  Qdrant     MinIO         Embeddings     Ollama        Nube LLM
 (datos)  (vectores) (archivos)        (TEI)     (local, opc.)  (Groq/Gemini/
                                                                   OpenAI)
          └──────── siempre activos ────────┘   └──── según LLM_PROVIDER ────┘
```

> **Embeddings y LLM están separados:** puedes cambiar el LLM entre local y nube sin afectar la búsqueda semántica. Todos los servicios internos escuchan solo en `127.0.0.1`; la única entrada de red es Nginx.

## 📁 Estructura del proyecto

```
recruitai/
├── backend/                FastAPI + Python 3.11
│   ├── app/
│   │   ├── adapters/       Integraciones: LLM, PDF, Qdrant, MinIO
│   │   ├── api/routes/     Endpoints: auth, candidates, jobs, search, admin
│   │   ├── core/           Config, seguridad, privacidad (auditoría LPDP), uso LLM
│   │   ├── db/             Modelos SQLAlchemy
│   │   └── main.py
│   ├── alembic/            Migraciones de BD (corren solas al arrancar)
│   └── evals/              Tests de regresión + evaluaciones de IA
├── frontend/               Next.js 14 + TypeScript  (src/{app,components,lib})
├── infra/init-db.sql       Esquema inicial de PostgreSQL
├── scripts/start.ps1|.sh   Arranque inteligente (detecta LLM_PROVIDER)
├── docker-compose.yml      8 servicios
├── nginx.conf              Reverse proxy (única entrada)
├── AGENTS.md               Reglas operativas del repo (fuente de verdad)
└── README.md
```

## 🔐 Seguridad

Todos los endpoints requieren autenticación JWT. Defensas alineadas con OWASP LLM Top 10:

- **Anti prompt-injection** (5 capas): patrones EN/ES, límites de longitud, escaneo de salida y de texto oculto en PDFs.
- **Validación de archivos**: MIME real, rechazo de PDF con JavaScript y DOCX con macros, límite 50 MB, deduplicación SHA-256.
- **PII masking** automático antes de enviar a un LLM en la nube (cumplimiento LPDP Perú).
- **Auditoría** (`audit_logs`) de cada acción sensible · **rate limiting** en login/upload · arranque bloqueado en producción si hay contraseñas por defecto.

> 🔒 **Dependencias:** `axios` está fijado en `1.13.6` (las versiones `1.14.1` y `0.30.4` fueron comprometidas en marzo 2026). No actualizar sin revisar el changelog de seguridad.
>
> Detalle técnico: [docs/SECURITY_PROMPT_INJECTION.md](docs/SECURITY_PROMPT_INJECTION.md).

## 🩺 Problemas comunes

| Síntoma | Causa / solución |
|---------|------------------|
| "No se pudo conectar con el servidor" | Entra por **http://localhost** (no `:3000`). Revisa `.\scripts\start.ps1 status`. |
| "El sistema de análisis está saturado" | Cuota gratis de la nube agotada. Cambia de modelo o usa `LLM_PROVIDER=ollama`. |
| El frontend no refleja cambios (Windows) | `docker restart recruitai-frontend` (el hot-reload no funciona en Windows). |
| Ollama lento en el primer CV | Normal: el modelo tarda 20-30 s en cargar a la GPU (cold start). El resto va rápido. |
| "Debes asociar el CV a una vacante" | Crea o selecciona la vacante antes de subir el CV. |
| Error 413 al subir | El archivo supera 50 MB. |

```bash
# Comandos útiles
docker logs recruitai-backend -f          # ver logs
docker exec recruitai-ollama ollama list  # modelos instalados (modo Ollama)
docker compose down                        # detener (sin borrar datos)
docker compose down -v                     # reset total (BORRA todos los datos)
```

## 🏭 Producción

```bash
openssl rand -hex 32                                                                       # JWT_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
```

```env
ENVIRONMENT=production            # el backend NO arranca con contraseñas por defecto
JWT_SECRET=<generado>
ENCRYPTION_KEY=<generado>         # requerido si usas LLM en la nube (PII masking)
POSTGRES_PASSWORD=<fuerte>
ADMIN_INITIAL_PASSWORD=<fuerte>
RECRUITER_INITIAL_PASSWORD=<fuerte>
```

> Requisitos de hardware con Ollama local: GPU NVIDIA 6+ GB VRAM, 16 GB RAM, 25 GB de disco. Sin GPU, Ollama corre en CPU (~2-3 min por CV) — en ese caso conviene usar un proveedor en la nube.

---

## 👤 Autor

**Jose Alarcon** — Cientifico de Datos

---

<p align="center"><sub>🤖 La IA sugiere; el reclutador decide.</sub></p>
