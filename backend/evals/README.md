# Evals — Medición objetiva del sistema IA

Framework de evaluación basado en **[Inspect AI](https://inspect.aisi.org.uk/)**
del UK AI Security Institute (MIT, adoptado por Anthropic, DeepMind, METR,
Apollo Research y AISIs de US/UK/EU/Japón/Korea).

## ¿Qué medimos?

Tres tareas, cada una con su dataset golden propio:

| Task | Qué evalúa | Métrica principal |
|---|---|---|
| `cv_extraction` | Extracción de campos de CVs (PDF/DOCX → JSON estructurado) | **F1 por campo** (nombre, email, experiencias, educación, skills, idiomas) |
| `job_profile_extraction` | Extracción de campos de perfiles de puesto | F1 por campo (título, departamento, skills, requisitos, etc.) |
| `candidate_matching` | Calidad del matching candidato vs vacante | Diferencia de score + match de recomendación + F1 de skills faltantes |

## Estructura

```
evals/
├── datasets/                      # ground truth versionado en git
│   ├── cv_extraction_golden.jsonl
│   ├── job_profile_golden.jsonl
│   └── matching_golden.jsonl
├── tasks/                         # @task definiciones
│   ├── cv_extraction.py
│   ├── job_profile_extraction.py
│   └── candidate_matching.py
├── scorers/                       # métricas custom
│   └── field_f1.py
├── solvers/                       # solver compartido que invoca LLMEngine
│   └── recruitai.py
├── run.sh                         # script de conveniencia
└── README.md                      # este archivo
```

**Nota de diseño**: los solvers (en `solvers/recruitai.py`) llaman directamente
a `LLMEngine.extract_resume()`, `extract_job_profile()` y
`reason_candidate_match()` — es decir, miden el **sistema completo**
(con su prompt, PII masking, strip_markdown_noise, etc.), no el LLM aislado.

## Cómo correr

Requiere el container `recruitai-backend` corriendo. La primera vez instala
las dependencias de evals automáticamente.

```bash
# Todo (CVs + perfiles + matching)
docker exec recruitai-backend bash /app/evals/run.sh

# Una sola tarea
docker exec recruitai-backend bash /app/evals/run.sh cv
docker exec recruitai-backend bash /app/evals/run.sh job
docker exec recruitai-backend bash /app/evals/run.sh match

# Modo manual (más control)
docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py
docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py --limit 5
docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py --log-format json

# Comparar modelos
docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py \
    --model groq/llama-3.3-70b-versatile

docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py \
    --model google/gemini-2.5-flash
```

Los logs quedan en `evals/.logs/`. Para verlos en UI:

```bash
docker exec recruitai-backend inspect view --log-dir /app/evals/.logs
# luego abrir http://localhost:7575
```

## Cómo agregar un nuevo caso al dataset golden

### CVs

1. Toma el texto del CV (idealmente el `raw_text` que PyMuPDF4LLM produjo
   para un CV real; lo puedes sacar de la BD con
   `SELECT raw_text FROM candidates WHERE id = '...'`).
2. **Anonimízalo**: cambia nombre, email, teléfono, DNI por valores ficticios
   (NUNCA versionar datos reales en git → LPDP Perú).
3. Construye el JSON esperado a mano basándote en el schema de
   `ExtractedResume` (ver `app/domain/models.py`).
4. Agrega una línea al final de `datasets/cv_extraction_golden.jsonl`:

```jsonl
{"id": "cv_NNN_descripcion", "input": "texto del CV...", "target": "{\"datos_personales\": {...}, ...}"}
```

5. Corre el eval y verifica que la nueva entrada se cargó:

```bash
docker exec recruitai-backend inspect eval evals/tasks/cv_extraction.py
```

### Perfiles de puesto

Mismo patrón con `datasets/job_profile_golden.jsonl`. Schema esperado: ver
`ExtractedJobProfile` en `app/domain/models.py`.

### Matching

Cada sample define `{candidate, job}` (datos YA estructurados) y
`{expected_score, expected_recommendation, expected_missing_skills}`. El
matching se evalúa en aislado (sin pasar por el extractor).

Los valores `expected_*` los pone un **humano experto** (¿este candidato
está bien matcheado? ¿qué score le pondrías?). Es subjetivo pero
consistente entre runs.

## Métricas de éxito

Umbrales recomendados a partir del primer run de baseline:

| Métrica | Umbral mínimo | Objetivo |
|---|---|---|
| `cv_extraction.weighted_f1` | 0.80 | 0.90 |
| `job_profile_extraction.weighted_f1` | 0.85 | 0.92 |
| `candidate_matching.overall` | 0.70 | 0.85 |

Si alguna métrica cae bajo el umbral mínimo tras un cambio de prompt o
modelo, **NO se mergea el PR**.

## Reglas para mantener evals saludables

1. **Cada bug reportado por un cliente** = un nuevo caso en el dataset golden.
   Así prevenimos regresiones para siempre.
2. **Nunca etiquetes el output del LLM como ground truth**. El gold se hace
   a mano por un humano. Si no, el sistema se auto-valida.
3. **Anonimiza los CVs antes de versionarlos**. Datos reales NO se commitean.
4. **No bajes los umbrales para hacer pasar el CI**. Si la métrica cayó,
   investiga y arregla; no oculta el problema.

## Más recursos

- [Inspect AI docs](https://inspect.aisi.org.uk/)
- [Hamel Husain — Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/)
- [Eugene Yan — Evaluating LLM-Evaluators](https://eugeneyan.com/writing/llm-evaluators/)
