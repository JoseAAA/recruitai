# RecruitAI

Sistema de reclutamiento con inteligencia artificial diseñado para equipos de Recursos Humanos. Sube CVs en PDF o DOCX, extrae automáticamente la información con un LLM local, y obtén un ranking explicado de candidatos para cada vacante.

Funciona **100% local** con Ollama (sin enviar datos a la nube) o con Gemini/OpenAI si prefieres mayor velocidad.

---

## ¿Qué hace?

1. **Creas una vacante** — describe el rol, sube el perfil de puesto en Word/PDF y el LLM extrae automáticamente todos los campos: título, skills, responsabilidades, experiencia mínima, idiomas requeridos, educación y descripción del rol
2. **Ajustas los pesos de evaluación** — por defecto skills 40% / experiencia 35% / educación 25%, configurable por vacante
3. **Subes CVs** — obligatorio asociarlos a una vacante; el LLM extrae nombre, email, teléfono, LinkedIn, skills, experiencia y formación académica / certificaciones
4. **Ejecutas el matching IA** — ranking de candidatos 0-100 con explicación en lenguaje natural, skills faltantes y recomendación
5. **Gestionas el pipeline** — vista tipo Kanban integrada en cada vacante con 4 etapas: Nuevos → Entrevista → Contratado / Descartado
6. **Operaciones masivas** — selecciona varios candidatos y rechaza, avanza o exporta a CSV de una sola vez

> Los CVs siempre se asocian a una vacante. Al eliminar una vacante, todos sus CVs se eliminan automáticamente (DB + vectores + archivos).

---

## Instalación (5 minutos)

### Prerrequisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git

No necesitas Python, Node.js ni ninguna dependencia adicional en tu máquina.

### 1. Clonar y configurar

```bash
git clone <url-del-repo>
cd analisis-cv
cp .env.example .env
```

Abre `.env` y configura como mínimo:

```env
JWT_SECRET=pon-aqui-cualquier-cadena-larga-y-aleatoria
ADMIN_INITIAL_PASSWORD=tu-password-seguro
RECRUITER_INITIAL_PASSWORD=tu-password-seguro
```

> En producción, contraseñas débiles bloquean el arranque del backend con un error explícito.

### 2. Arrancar

```bash
docker compose up -d
```

La primera vez descarga las imágenes de Docker (~2-3 GB). Espera unos minutos.

### 3. Instalar los modelos de IA

```bash
# Modelo para extraer datos de CVs y hacer matching (~2.5 GB)
docker exec recruitai-ollama ollama pull gemma3:4b

# Modelo para embeddings / búsqueda semántica (~270 MB)
docker exec recruitai-ollama ollama pull nomic-embed-text
```

### 4. Acceder

| Servicio | URL |
|----------|-----|
| Dashboard | http://localhost |
| API Docs (Swagger) | http://localhost:8000/docs |
| MinIO (archivos) | http://localhost:9001 |

**Usuarios por defecto** (configurados en `.env`):
- Admin: `admin@recruitai.com` / `<ADMIN_INITIAL_PASSWORD>`
- Reclutador: `recruiter@recruitai.com` / `<RECRUITER_INITIAL_PASSWORD>`

---

## Flujo de trabajo (principio 80/20)

El sistema resuelve el 80% del trabajo de análisis de CVs con el flujo mínimo:

```
1. Crear vacante  →  /jobs/new
   ↳ Arrastra el Word/PDF del perfil del puesto → el LLM rellena todos los campos
   ↳ Revisa y ajusta skills requeridos (son los más importantes para el scoring)
   ↳ Opcional: personaliza los pesos skills/experiencia/educación

2. Subir CVs  →  /data  (o desde la página de la vacante → "Importar CVs")
   ↳ Selecciona la vacante antes de subir — es obligatorio
   ↳ La IA extrae automáticamente toda la información del CV
   ↳ Subida en paralelo de múltiples archivos

3. Analizar  →  /jobs → [vacante] → pestaña "Ranking IA" → "Analizar con IA"
   ↳ Ranking 0-100 con explicación por candidato
   ↳ Skills presentes vs faltantes
   ↳ Recomendación: Altamente recomendado / Buena opción / Considerar / No recomendado

4. Gestionar pipeline  →  /jobs → [vacante] → pestaña "Pipeline"
   ↳ Vista Kanban con 4 columnas: Nuevos · Entrevista · Contratado · Descartado
   ↳ Score IA visible en cada tarjeta (si ya se ejecutó el matching)
   ↳ Botones de acción rápida para mover al candidato entre etapas
   ↳ Operaciones masivas: selecciona varios → rechazar / avanzar / exportar CSV
```

---

## Navegación

| Sección | Ruta | Descripción |
|---------|------|-------------|
| Panel de Control | `/` | KPIs: total CVs, vacantes activas, candidatos nuevos esta semana |
| Perfiles de Puesto | `/jobs` | Lista de vacantes con conteo de CVs y opción de matching rápido |
| Detalle de Vacante | `/jobs/[id]` | 3 pestañas: Requisitos · Pipeline · Ranking IA |
| Candidatos | `/candidates` | Listado global con filtros, selección múltiple y exportación CSV |
| Importar CVs | `/data` | Carga masiva de CVs asociada a una vacante |
| Analítica | `/analytics` | Estadísticas históricas del proceso de reclutamiento |

### Pestaña "Pipeline" dentro de cada vacante

El pipeline vive **dentro del perfil del puesto**, no como página separada. Esto refleja el flujo natural de RRHH: "abro esta vacante → veo en qué etapa está cada candidato para este puesto".

| Columna | Estados internos que agrupa | Cuándo usar |
|---------|---------------------------|-------------|
| Nuevos | `new`, `screening`, `shortlisted` | CV recién subido, pendiente de revisar |
| Entrevista | `interview` | Seleccionado para entrevistar |
| Contratado | `hired`, `offer` | Decisión positiva tomada |
| Descartado | `rejected` | No avanza en este proceso |

---

## Creación de vacante: qué llena el LLM vs. qué configura RRHH

| Campo | Quién lo llena | Impacto en scoring |
|-------|---------------|-------------------|
| Título del puesto | LLM + revisión | Embedding semántico |
| Descripción del rol | LLM + revisión | **Matching semántico principal** |
| Habilidades requeridas | LLM + revisión | **40% del puntaje (configurable)** |
| Habilidades deseables | LLM + revisión | Bonus skills en match |
| Experiencia mínima (años) | LLM + revisión | **Parte del score de experiencia** |
| Formación académica | LLM + revisión | **25% del puntaje (configurable)** |
| Responsabilidades | LLM + revisión | Embedding semántico |
| Objetivos clave | LLM + revisión | Embedding semántico |
| Idiomas requeridos | LLM + revisión | Match de idiomas del candidato |
| Departamento | LLM o RRHH | Solo organizativo — no afecta scoring |
| Modalidad / Industria | LLM | Solo informativo |
| **Pesos de scoring** | **Solo RRHH** | Cada empresa pondera diferente según el rol |

---

## Configuración de modelos de IA

### Ollama local (por defecto) — privacidad total

Los datos nunca salen de tu máquina.

```env
LLM_PROVIDER=ollama
EXTRACTION_MODEL=gemma3:4b      # Lee y estructura los CVs
MATCH_MODEL=gemma3:4b           # Evalúa candidatos vs vacante
EMBEDDING_MODEL=nomic-embed-text
```

**Modelos alternativos:**

| Modelo | VRAM | Velocidad | Calidad |
|--------|------|-----------|---------|
| `gemma3:4b` (defecto) | ~3 GB | Media | Buena |
| `qwen2.5:3b` | ~2 GB | Rápida | Aceptable |
| `llama3.2:3b` | ~2 GB | Rápida | Aceptable |

```bash
docker exec recruitai-ollama ollama pull qwen2.5:3b
# Actualizar EXTRACTION_MODEL y MATCH_MODEL en .env
docker restart recruitai-backend
```

### Gemini (nube) — más rápido, sin GPU

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu-api-key-aqui
GEMINI_MODEL=gemini-2.0-flash
PII_MASKING_ENABLED=true   # Anonimiza datos antes de enviar a la nube
```

Obtén tu API Key gratis en [aistudio.google.com](https://aistudio.google.com).
Tier gratuito: 1,500 requests/día — suficiente para ~500 CVs/día.

---

## Seguridad

Todos los endpoints requieren autenticación JWT. El sistema incluye capas de defensa contra los riesgos del OWASP LLM Top 10:

| Capa | Mecanismo | Qué protege |
|------|-----------|-------------|
| **Autenticación** | JWT en todos los endpoints | Acceso no autorizado |
| **Rate limiting** | 10 req/min en upload y login (`slowapi`) | Fuerza bruta y abuso |
| **Tamaño de body** | Máximo 50 MB | DoS por archivos grandes |
| **Magic bytes** | Validación de PDF/DOCX real | Archivos maliciosos disfrazados |
| **Deduplicación** | Hash SHA-256 por CV + job | Subidas duplicadas |
| **Prompt injection** | 37+ patrones regex bloqueantes (5 capas) | CVs con instrucciones maliciosas |
| **Output scanning** | Patrones de compromiso en respuesta LLM | Jailbreak exitoso |
| **PII Masking** | Anonimización antes de LLMs cloud | Fuga de datos personales |
| **Audit log** | Tabla `audit_logs` en PostgreSQL | Trazabilidad LPDP Perú |
| **CORS** | Métodos y headers restringidos | Cross-origin attacks |
| **Credenciales seguras** | Bloqueo de arranque en producción si detecta defaults | Despliegues inseguros |

> **Nota de seguridad de dependencias:** `axios` está fijado en `1.13.6` sin caret (`^`). Las versiones `1.14.1` y `0.30.4` fueron comprometidas en marzo 2026 (ataque a la cadena de suministro, RAT norcoreano). No actualizar hasta verificar que la versión objetivo es segura.

Ver detalle técnico en [docs/SECURITY_PROMPT_INJECTION.md](docs/SECURITY_PROMPT_INJECTION.md).

---

## Requisitos de hardware

### Con Ollama local (recomendado)

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| GPU NVIDIA | 4 GB VRAM | 6+ GB VRAM |
| RAM | 8 GB | 16 GB |
| Disco | 15 GB libres | 25 GB libres |

> Sin GPU NVIDIA, Ollama funciona en CPU pero es lento (~2-3 min por CV). Considera usar Gemini en ese caso.

### Con Gemini (nube)

Cualquier máquina con Docker funciona. No necesitas GPU.

---

## Comandos útiles

```bash
# Ver estado de todos los contenedores
docker compose ps

# Logs en tiempo real
docker logs recruitai-backend -f
docker logs recruitai-frontend -f

# Recargar código tras editar (Windows — hot reload no funciona)
docker restart recruitai-backend
docker restart recruitai-frontend

# Modelos Ollama instalados
docker exec recruitai-ollama ollama list

# Detener todo (sin borrar datos)
docker compose down

# Reset completo (borra todos los datos)
docker compose down -v
```

---

## Arquitectura

```
Navegador → http://localhost
               │
           ┌───┴───┐
           │ Nginx │  Reverse proxy
           └───┬───┘
        ┌──────┴───────┐
        ▼              ▼
   Next.js :3000    FastAPI :8000
   (UI / frontend)  (API + MCP Server)
                        │
          ┌─────────────┼──────────────┬──────────┐
          ▼             ▼              ▼           ▼
     PostgreSQL      Qdrant          MinIO       Ollama
     (datos          (vectores       (archivos   (LLM
     relacionales)   semánticos)     CV/PDF)     local)
```

**Stack:**
- Backend: Python 3.11, FastAPI, SQLAlchemy async, Pydantic v2, `slowapi` rate limiting
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind CSS, axios 1.13.6
- Base de datos: PostgreSQL 15 (incluye tabla `audit_logs` para trazabilidad LPDP)
- Búsqueda semántica: Qdrant (4 vectores por candidato: `experience`, `education`, `skills`, `summary`)
- Almacenamiento de archivos: MinIO (S3-compatible)
- LLM local: Ollama con gemma3:4b
- MCP Server: expone la API en `http://localhost:8000/mcp` para Claude Desktop / Cursor

### Modelos de base de datos clave

| Tabla | Descripción |
|-------|-------------|
| `candidates` | CV extraído — incluye `job_id FK` (obligatorio) |
| `job_profiles` | Vacante — incluye `scoring_config JSON` (pesos personalizados) |
| `match_results` | Scores IA persistidos (no se recalculan en cada visita) |
| `candidate_notes` | Notas de RRHH: general, entrevista, feedback, cambio de estado |
| `audit_logs` | Log de acciones para cumplimiento LPDP Perú |

---

## Deploy en producción

### 1. Generar claves seguras

```bash
# JWT Secret
openssl rand -hex 32

# Encryption Key (para PII masking con Gemini/OpenAI)
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

> En `ENVIRONMENT=production`, el backend rechaza arrancar si detecta valores por defecto en `JWT_SECRET`, `ADMIN_INITIAL_PASSWORD` o `RECRUITER_INITIAL_PASSWORD`.

---

## Solución de problemas

**El frontend no muestra los cambios tras editar código (Windows)**
```bash
docker restart recruitai-frontend
```
El hot reload de Next.js no detecta cambios del host en Windows por limitaciones de inotify.

**Ollama responde lento en el primer CV**
Normal. El modelo tarda 20-30 segundos en cargarse a VRAM (cold start). A partir del segundo CV va mucho más rápido.

**Error al subir un CV: "Debes asociar el CV a una vacante"**
Es obligatorio seleccionar una vacante al subir un CV. Crea primero la vacante desde `/jobs/new` o `/jobs`.

**Error al hacer matching: "Sin candidatos para analizar"**
Los CVs deben haber sido subidos con esa vacante seleccionada. Verifica desde la pestaña "Pipeline" de la vacante.

**El campo "Descripción del puesto" quedó vacío tras analizar el documento**
Si el LLM no genera descripción, el sistema usa automáticamente el primer párrafo sustancial del documento. Si sigue vacío, el documento podría no tener párrafos de descripción — escríbela manualmente.

**Error 413 al subir CV**
El archivo supera el límite de 50 MB. Los CVs normales no deberían llegar a ese tamaño.

**Error 400 al subir CV: "contenido potencialmente malicioso"**
El texto del documento activó el detector de prompt injection. El archivo podría contener instrucciones dirigidas al sistema de IA.

**Extracción incorrecta de email o teléfono**
El LLM solo extrae valores que aparecen literalmente en el texto del CV. Si el email/teléfono está en una imagen o formato no estándar, puede no detectarse.

**Las versiones de los paquetes npm no se actualizan solas**
Intencional. `axios` está fijado en `1.13.6` sin `^` para evitar actualizaciones automáticas a versiones comprometidas. Actualizar manualmente solo tras verificar el changelog de seguridad.

---

## Licencia

MIT
