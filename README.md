# RecruitAI

Sistema de reclutamiento con inteligencia artificial. Sube CVs en PDF o DOCX, extrae automáticamente la información con un LLM, y obtén un ranking de candidatos explicado para cada vacante.

Funciona **100% local** con Ollama (sin enviar datos a la nube) o con Gemini/OpenAI si prefieres la nube.

---

## ¿Qué hace?

1. **Subes CVs** → el sistema extrae nombre, email, skills, experiencia y educación automáticamente
2. **Creas una vacante** con los requisitos y pesos de evaluación personalizados (ej: skills 60%, experiencia 40%)
3. **Ejecutas el matching IA** → obtienes un ranking de candidatos con puntuación, explicación y skills faltantes
4. **Generas preguntas de entrevista** para cada candidato directamente desde el resultado del matching
5. **Gestionas el pipeline** de reclutamiento: preseleccionar, programar entrevista, rechazar, agregar notas

---

## Instalación (5 minutos)

### Prerrequisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git

Eso es todo. No necesitas Python, Node.js ni ninguna dependencia adicional en tu máquina.

### 1. Clonar y configurar

```bash
git clone <url-del-repo>
cd analisis-cv
cp .env.example .env
```

Abre `.env` y cambia al menos esto:

```env
JWT_SECRET=pon-aqui-cualquier-cadena-larga-y-aleatoria
```

### 2. Arrancar

```bash
docker compose up -d
```

La primera vez descarga las imágenes de Docker (~2-3 GB). Espera unos minutos.

### 3. Instalar los modelos de IA

El sistema usa Ollama con dos modelos. Instálalos después de que los contenedores estén corriendo:

```bash
# Modelo para extraer datos de CVs y hacer matching
docker exec recruitai-ollama ollama pull gemma3:4b

# Modelo para embeddings (búsqueda semántica)
docker exec recruitai-ollama ollama pull nomic-embed-text
```

> La primera descarga tarda 5-10 minutos dependiendo tu internet (~2.5 GB en total).

### 4. Acceder

| Servicio | URL |
|----------|-----|
| Dashboard | http://localhost |
| API Docs (Swagger) | http://localhost:8000/docs |
| MinIO (archivos) | http://localhost:9001 |

**Usuarios por defecto:**
- Admin: `admin@recruitai.com` / `change-me-on-first-run`
- Reclutador: `recruiter@recruitai.com` / `change-me-on-first-run`

> Cambia las contraseñas en `.env` antes de exponer el sistema a internet: `ADMIN_INITIAL_PASSWORD` y `RECRUITER_INITIAL_PASSWORD`.

---

## Flujo de trabajo típico

```
1. Crear vacante  →  /jobs/new
   - Título, skills requeridos, nivel de seniority
   - Ajustar pesos de evaluación (skills / experiencia / educación)

2. Subir CVs  →  /data  (o desde la página de la vacante)
   - Arrastra PDFs o DOCXs
   - Selecciona la vacante a la que pertenecen
   - La IA extrae todo automáticamente

3. Ver matching  →  /jobs → [vacante] → "Analizar con IA"
   - Ranking de candidatos con puntuación 0-100
   - Explicación en lenguaje natural
   - Skills que tiene vs skills que faltan
   - Botón "Preguntas IA" para generar preguntas de entrevista personalizadas

4. Gestionar pipeline  →  /candidates/[id]
   - Cambiar estado: Preseleccionar / Programar entrevista / Rechazar
   - Agregar notas de llamadas o entrevistas
   - Rating 1-5 estrellas
```

---

## Configuración de modelos de IA

El archivo `.env` controla qué modelos se usan. Solo edita ese archivo, no hace falta tocar código.

### Ollama local (por defecto) — privacidad total

Los datos nunca salen de tu máquina.

```env
LLM_PROVIDER=ollama
EXTRACTION_MODEL=gemma3:4b    # Lee y estructura los CVs
MATCH_MODEL=gemma3:4b         # Evalúa candidatos vs vacante
EMBEDDING_MODEL=nomic-embed-text
```

**Modelos alternativos:**

| Modelo | VRAM | Velocidad | Calidad |
|--------|------|-----------|---------|
| `gemma3:4b` (defecto) | ~3 GB | Media | Buena |
| `qwen3.5:2b` | ~2 GB | Rápida | Aceptable |
| `qwen3.5:4b` | ~3 GB | Media | Buena |

Para cambiar de modelo:
```bash
# Descargar el nuevo modelo
docker exec recruitai-ollama ollama pull qwen3.5:2b

# Cambiar en .env
EXTRACTION_MODEL=qwen3.5:2b
MATCH_MODEL=qwen3.5:2b

# Reiniciar el backend
docker restart recruitai-backend
```

### Gemini (nube) — más rápido, sin GPU

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu-api-key-aqui
GEMINI_MODEL=gemini-2.0-flash
PII_MASKING_ENABLED=true   # Recomendado: anonimiza datos antes de enviar a la nube
```

Obtén tu API Key gratis en [aistudio.google.com](https://aistudio.google.com) → "Get API Key".
Tier gratuito: 1,500 requests/día — suficiente para ~500 CVs/día.

---

## Requisitos de hardware

### Con Ollama local (recomendado)

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| GPU NVIDIA | 4 GB VRAM | 6+ GB VRAM |
| RAM | 8 GB | 16 GB |
| Disco | 10 GB libres | 20 GB libres |

> Sin GPU NVIDIA, Ollama funciona en CPU pero es muy lento (~2-3 minutos por CV). Considera usar Gemini en ese caso.

### Con Gemini (nube)

Cualquier máquina con Docker funciona. No necesitas GPU.

---

## Comandos útiles

```bash
# Ver estado de todos los contenedores
docker compose ps

# Ver logs en tiempo real
docker logs recruitai-backend -f
docker logs recruitai-frontend -f

# Reiniciar un servicio específico (necesario tras editar código en Windows)
docker restart recruitai-backend
docker restart recruitai-frontend

# Ver qué modelos están instalados en Ollama
docker exec recruitai-ollama ollama list

# Detener todo (sin borrar datos)
docker compose down

# Detener y borrar todos los datos (reset completo)
docker compose down -v
```

---

## Arquitectura

```
┌─────────────┐    http://localhost
│   Nginx     │◄─────────────────────── Navegador
│(proxy :80)  │
└──────┬──────┘
       ├──► Frontend (Next.js :3000)   → UI del sistema
       └──► Backend  (FastAPI :8000)   → API REST + MCP Server
                  │
         ┌────────┼────────┬────────────┐
         ▼        ▼        ▼            ▼
     PostgreSQL  Qdrant   MinIO       Ollama
     (datos)   (vectores) (archivos)  (LLM local)
```

**Stack:**
- Backend: Python 3.11 + FastAPI + SQLAlchemy (async) + Pydantic
- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- Base de datos: PostgreSQL 15
- Búsqueda semántica: Qdrant (base de datos vectorial)
- Almacenamiento de archivos: MinIO (S3-compatible)
- LLM local: Ollama con gemma3:4b

**MCP Server:** El backend expone sus herramientas como servidor MCP en `http://localhost:8000/mcp`, compatible con Claude Desktop, Cursor y otros clientes AI.

---

## Deploy en producción

### 1. Generar claves seguras

```bash
# JWT Secret
openssl rand -hex 32

# Encryption Key (para PII masking)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configurar `.env` para producción

```env
ENVIRONMENT=production
JWT_SECRET=<generado-con-openssl>
ENCRYPTION_KEY=<generado-con-fernet>
POSTGRES_PASSWORD=<password-fuerte>
ADMIN_INITIAL_PASSWORD=<password-fuerte>
RECRUITER_INITIAL_PASSWORD=<password-fuerte>

# Si usas Gemini en producción:
LLM_PROVIDER=gemini
GEMINI_API_KEY=<tu-api-key>
PII_MASKING_ENABLED=true
```

### 3. Arrancar con el compose de producción

```bash
docker compose -f docker-compose.prod.yml up -d
```

La imagen de producción incluye Ollama y no monta el código fuente como volumen.

---

## Solución de problemas

**Los CVs se procesan con 0 años de experiencia**
El modelo puede no haber extraído las fechas. Sube de nuevo el CV — el prompt incluye reglas específicas para extraer `fecha_inicio` y `fecha_fin`.

**El frontend no muestra los cambios que hice en el código**
En Windows, el hot-reload de Next.js no detecta cambios del host:
```bash
docker restart recruitai-frontend
```

**Ollama responde muy lento**
El modelo se está cargando desde disco (cold start, ~20-30 segundos el primer CV). A partir del segundo CV va mucho más rápido porque el modelo queda en VRAM.

**Error 413 al subir un CV**
El archivo supera el límite de 50 MB. Los CVs normales no deberían superar ese tamaño.

**Error al hacer matching: "Sin candidatos para analizar"**
Los CVs deben estar asociados a la vacante al momento de subirlos. Desde la página de la vacante → "Importar CVs", o al subir en `/data` selecciona la vacante en el selector.

---

## Licencia

MIT
