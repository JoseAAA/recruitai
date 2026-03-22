# RecruitAI 🚀

Sistema de reclutamiento con IA para análisis automático de CVs y matching inteligente de candidatos.

## ⚡ Inicio Rápido (5 minutos)

### Prerrequisitos
- Docker & Docker Compose
- API Key de Google Gemini (gratis)

### 1. Configuración

```bash
# Clonar y configurar
cp .env.example .env
```

Edita `.env` y agrega:
```env
GEMINI_API_KEY=tu-api-key-aqui
JWT_SECRET=genera-una-clave-segura-aqui
```

> 💡 **Obtener API Key GRATIS**: [aistudio.google.com](https://aistudio.google.com) → "Get API Key"

### 2. Iniciar (Desarrollo)

```bash
docker compose up -d
```

### 3. Acceder

| Servicio | URL |
|----------|-----|
| 🖥️ Dashboard | http://localhost:80 |
| 📡 API Docs | http://localhost:8000/docs |
| 🤖 MCP Server | http://localhost:8000/mcp |

---

## ✨ Características

### Análisis Automático de CVs
- **Subida PDF/DOCX** → Extracción automática con IA
- **Datos estructurados**: Nombre, email, skills, experiencia
- **Seguridad**: Protección anti-prompt injection (3 capas)

### Matching Inteligente
- **Búsqueda semántica** con embeddings reales
- **Scoring explicable** con gráficos radar
- **Ranking por relevancia** a requisitos del puesto

### Gestión Completa
- **Candidatos**: CRUD, filtros, notas, rating
- **Vacantes**: Requisitos, skills, matching IA
- **Dashboard**: KPIs, alertas, top candidatos

---

## 🔒 Seguridad & Privacidad

### Cumplimiento LPDP Perú (Ley 29733)
- **PII Masking**: Datos personales se anonimizan antes de enviar a la IA
- **Encriptación**: AES-256 para datos sensibles
- **Auditoría**: Registro de accesos a datos personales
- **Retención**: Políticas de eliminación automática (2 años)

### Protección de Datos en LLM
```
CV Original     →   PII Masker    →   CV Anónimo     →   Gemini API
"Juan Pérez"        (Presidio)        "[PERSON_1]"        (procesa)
                         ↓
                  Mapping Encriptado
                  (AES-256/Fernet)
```

### Defensa Anti-Prompt Injection
- **22+ patrones** de detección
- **Límites de longitud** (50K caracteres)
- **Validación de output** (campos requeridos)

---

## 🤖 Configuración de IA

### Gemini (Recomendado - Tier Gratuito)
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu-api-key
GEMINI_MODEL=gemini-2.0-flash
```

**Costos estimados:**
- Tier gratuito: 1,500 requests/día
- 100 CVs/día ≈ $0.04/día ($1.20/mes)

### Ollama Local con Qwen 3.5 (Privacidad Total)
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3.5:2b
```

**Requisitos**: GPU NVIDIA ~3GB VRAM. Instalar modelo:
```bash
ollama pull qwen3.5:2b
```

> 💡 **Qwen 3.5 es multimodal nativo** — el mismo modelo procesa texto e imágenes. Un solo modelo para todo.

---

## 🔌 MCP Server (AI Agent Integration)

RecruitAI expone un servidor **MCP (Model Context Protocol)** que permite a cualquier cliente AI interactuar con el sistema:

| Cliente | Cómo Conectar |
|---------|---------------|
| Claude Desktop | Agregar URL `http://localhost:8000/mcp` en Settings |
| Cursor | Configurar MCP server en settings.json |
| ChatGPT | Usar con plugins MCP |

**Tools disponibles** (auto-descubiertas):
- Upload CV y extracción automática
- Búsqueda semántica de candidatos
- Crear/gestionar vacantes
- Matching candidato-puesto
- Generar preguntas de entrevista
- Dashboard y estadísticas

---

## 🏗️ Arquitectura

```
┌──────────────────────┐
│  AI Clients          │
│  (Claude/Cursor/etc) │
└──────────┬───────────┘
           │ MCP Protocol
┌──────────▼───────────┐     ┌─────────────────┐
│    Frontend          │────▶│     Nginx       │
│   (Next.js)          │     │  (Reverse Proxy)│
└──────────────────────┘     └────────┬────────┘
                                      │
                             ┌────────▼────────┐
                             │     Backend     │──── PII Masker
                             │  (FastAPI+MCP)  │     (Presidio)
                             └───┬────┬────┬───┘
                                 │    │    │
               ┌─────────────────┤    │    ├──────────────┐
               ▼                 ▼    │    ▼              ▼
         ┌──────────┐      ┌──────────┐  ┌────────────────────┐
         │  Qdrant  │      │ Postgres │  │  LLM Provider      │
         │(Vectors) │      │ (Data)   │  │  (Gemini/OpenAI/   │
         └──────────┘      └──────────┘  │   Qwen3.5 Local)   │
                                         └────────────────────┘
```

---

## 🚀 Deploy en Producción

### 1. Generar claves seguras

```bash
# JWT Secret
openssl rand -hex 32

# Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configurar .env

```env
ENVIRONMENT=production
JWT_SECRET=<tu-jwt-generado>
ENCRYPTION_KEY=<tu-fernet-key>
GEMINI_API_KEY=<tu-api-key>
POSTGRES_PASSWORD=<password-seguro>
```

### 3. Iniciar en producción

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## 📁 Estructura del Proyecto

```
├── backend/
│   ├── app/
│   │   ├── adapters/      # LLM, embeddings, Qdrant, PII masker
│   │   ├── api/routes/    # Endpoints REST
│   │   ├── core/          # Config, security, privacy
│   │   └── domain/        # Models
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── app/           # Pages
│       ├── components/    # React components
│       └── lib/           # API client
│
├── docker-compose.yml          # Desarrollo
├── docker-compose.prod.yml     # Producción
└── .env.example
```

---

## 🧪 Desarrollo Local

### Backend
```bash
cd backend
pip install -r requirements.txt
# Instalar modelo de NLP para PII
python -m spacy download es_core_news_sm
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 📝 Licencia

MIT
