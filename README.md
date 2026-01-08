# RecruitAI 🚀

Sistema de reclutamiento con IA para análisis automático de CVs y matching inteligente de candidatos.

## ⚡ Inicio Rápido (5 minutos)

### Prerrequisitos
- Docker & Docker Compose
- Una API Key de Google Gemini (gratis)

### 1. Configuración

```bash
# Clonar y configurar
cp .env.example .env
```

Edita `.env` y agrega tu API key de Gemini:
```env
GEMINI_API_KEY=tu-api-key-aqui
```

> 💡 **Obtener API Key GRATIS**: [aistudio.google.com](https://aistudio.google.com) → "Get API Key" → Crear nueva key

### 2. Iniciar

```bash
docker compose up -d
```

### 3. Acceder

| Servicio | URL |
|----------|-----|
| 🖥️ Dashboard | http://localhost:80 |
| 📡 API Docs | http://localhost:8000/docs |

---

## ✨ Características

### Análisis Automático de CVs
- **Subida PDF/DOCX** → Extracción automática con IA
- **Datos estructurados**: Nombre, email, skills, experiencia, educación
- **Seguridad**: Protección contra prompt injection en 3 capas

### Matching Inteligente
- **Búsqueda semántica** con embeddings (sentence-transformers)
- **Scoring explicable** con gráficos radar
- **Ranking por relevancia** a requisitos del puesto

### Gestión Completa
- **Candidatos**: CRUD, filtros, notas, rating
- **Vacantes**: Requisitos, skills, matching
- **Dashboard**: KPIs, alertas, top candidatos

---

## 🤖 Configuración de IA

### Opción 1: Gemini (Recomendado - Gratis)
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu-api-key
```

### Opción 2: OpenAI (Pago)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Opción 3: Local con Ollama (Gratis, requiere GPU)
```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

---

## 🏗️ Arquitectura

```
┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│     Nginx       │
│   (Next.js)     │     │  (Reverse Proxy)│
└─────────────────┘     └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │     Backend     │
                        │    (FastAPI)    │
                        └───┬────┬────┬───┘
                            │    │    │
              ┌─────────────┤    │    ├─────────────┐
              ▼             ▼    │    ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  Qdrant  │  │ Postgres │  │  LLM API │
        │(Vectors) │  │ (Data)   │  │(Gemini/OA)│
        └──────────┘  └──────────┘  └──────────┘
```

---

## 🔒 Seguridad

- **Prompt Injection Defense**: 3 capas de protección
  - Patrones sospechosos (22+ regex)
  - Límites de longitud (50K caracteres)
  - Validación de output
- **JWT Authentication**
- **CORS configurado**
- **Tokens OAuth encriptados** (Fernet)

---

## 📁 Estructura del Proyecto

```
├── backend/           # API FastAPI
│   ├── app/
│   │   ├── adapters/  # LLM, embeddings, Qdrant
│   │   ├── api/       # Routes
│   │   ├── core/      # Config, security
│   │   └── domain/    # Models
│   └── requirements.txt
│
├── frontend/          # Next.js UI
│   └── src/
│       ├── app/       # Pages
│       ├── components/# React components
│       └── lib/       # API client
│
├── docker-compose.yml
└── .env.example       # Template de configuración
```

---

## 🧪 Desarrollo Local

### Backend
```bash
cd backend
pip install -r requirements.txt
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
