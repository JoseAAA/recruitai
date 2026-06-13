"""Medición de consumo real de tokens del pipeline (para estimar costos).

Construye el prompt REAL de extracción con un CV típico y lo envía una vez,
leyendo usageMetadata de Gemini (tokens exactos de entrada/salida).
Uso: docker exec recruitai-backend python /tmp/measure_tokens.py
"""
import sys, asyncio, json
sys.path.insert(0, "/app")
import inspect

import httpx
import pymupdf
import pymupdf4llm

from app.core.config import settings
from app.prompts import render as render_prompt

MODEL = "gemini-3.5-flash"  # bucket con cuota disponible hoy


async def medir(nombre: str, system_msg: str, prompt: str, max_out: int) -> dict:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": f"{system_msg}\n\n{prompt}"}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": max_out,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
        )
        r.raise_for_status()
        u = r.json().get("usageMetadata", {})
        res = {
            "in": u.get("promptTokenCount", 0),
            "out": u.get("candidatesTokenCount", 0),
            "total": u.get("totalTokenCount", 0),
        }
        print(f"{nombre}: entrada={res['in']} salida={res['out']} total={res['total']}")
        return res


async def main():
    doc = pymupdf.open("/tmp/cv_tipico.pdf")
    sup = set(inspect.signature(pymupdf4llm.to_markdown).parameters)
    kw = {k: v for k, v in dict(ignore_code=True, show_progress=False).items() if k in sup}
    md = pymupdf4llm.to_markdown(doc, **kw)
    print(f"CV típico: {len(md)} caracteres de markdown")

    # 1. Extracción (el prompt real del sistema)
    p_ext = render_prompt("extract_cv", cv_text=md)
    s_ext = render_prompt("extract_cv_system")
    ext = await medir("EXTRACCIÓN", s_ext, p_ext, 4000)

    # 2. Matching (prompt real con datos estructurados típicos)
    p_match = render_prompt(
        "match_candidate",
        job_title="Científico de Datos",
        job_description="Diseñar e implementar modelos de ML y análisis estadístico que generen valor de negocio. Modalidad híbrida.",
        required_skills="Python, SQL, TensorFlow, XGBoost, Power BI",
        preferred_skills="Spark, NLP",
        min_experience_years=3,
        candidate_skills="Python, SQL, Excel, Power BI, Git, Docker, Azure",
        experience_block=json.dumps([
            {"cargo": "Analista de Datos Senior", "empresa": "ACME", "fecha_inicio": "2021-03", "fecha_fin": "Presente", "descripcion": "Modelos predictivos de demanda y dashboards ejecutivos para 5 unidades de negocio."},
            {"cargo": "Analista de Datos Junior", "empresa": "ACME", "fecha_inicio": "2019-01", "fecha_fin": "2021-02", "descripcion": "Limpieza y análisis exploratorio, reportes en Power BI."},
        ], ensure_ascii=False),
        education_block=json.dumps([
            {"institution": "UNI", "degree": "Ing. de Sistemas", "education_type": "educacion", "degree_status": "Titulado"},
        ], ensure_ascii=False),
        languages_block="Español (Nativo), Inglés (Intermedio)",
        candidate_summary="Analista de datos con 6 años de experiencia en retail.",
    )
    s_match = render_prompt("match_candidate_system")
    mat = await medir("MATCHING/candidato", s_match, p_match, 4000)

    print("\n=== RESUMEN PARA COSTEO ===")
    print(f"extract_in={ext['in']} extract_out={ext['out']}")
    print(f"match_in={mat['in']} match_out={mat['out']}")


asyncio.run(main())
