"""Promedio de tokens del pipeline sobre TODOS los CVs cargados.

Cuenta con el tokenizador real de cada proveedor (tiktoken o200k_base para
OpenAI; endpoint countTokens para Gemini — gratis, no consume cuota de
generación). La salida de extracción se estima serializando los datos
estructurados ya guardados de cada candidato (el JSON que produjo el LLM).

Uso: docker exec -e API_TOKEN=<jwt> recruitai-backend python /tmp/measure_multi.py
"""
import sys, os, json, statistics
sys.path.insert(0, "/app")

import httpx
import tiktoken

from app.core.config import settings
from app.prompts import render as render_prompt

API = "http://localhost:8000/api"
TOKEN = os.environ["API_TOKEN"]
HDR = {"Authorization": f"Bearer {TOKEN}"}
ENC = tiktoken.get_encoding("o200k_base")  # gpt-4o / 4o-mini / 4.1


def openai_count(text: str) -> int:
    return len(ENC.encode(text))


def gemini_count(client: httpx.Client, text: str) -> int:
    r = client.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:countTokens",
        headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": text}]}]},
    )
    r.raise_for_status()
    return r.json().get("totalTokens", 0)


def extraction_output_json(detail: dict) -> str:
    """Reconstruye (aprox) el JSON que el LLM produjo para este CV."""
    return json.dumps({
        "datos_personales": {
            "nombre_completo": detail.get("full_name"),
            "telefono": detail.get("phone"),
            "email": detail.get("email"),
            "linkedin": detail.get("linkedin"),
            "github": detail.get("github"),
        },
        "resumen_profesional": detail.get("summary"),
        "habilidades": detail.get("skills", []),
        "idiomas": detail.get("idiomas", []),
        "experiencia_profesional": detail.get("experience", []),
        "educacion": detail.get("education", []),
    }, ensure_ascii=False)


def main():
    with httpx.Client(timeout=60) as c:
        cands = c.get(f"{API}/candidates?page=1&page_size=100", headers=HDR).json()["items"]
        rows = []
        for it in cands:
            d = c.get(f"{API}/candidates/{it['id']}", headers=HDR).json()
            raw = d.get("raw_text") or ""
            if len(raw) < 300:
                continue
            prompt_in = render_prompt("extract_cv_system") + "\n\n" + render_prompt("extract_cv", cv_text=raw)
            out_json = extraction_output_json(d)
            rows.append({
                "name": (d.get("full_name") or "?")[:24],
                "chars": len(raw),
                "oa_in": openai_count(prompt_in),
                "oa_out": openai_count(out_json),
                "ge_in": gemini_count(c, prompt_in),
                "ge_out": gemini_count(c, out_json),
            })

        print(f"{'CV':24} {'chars':>6} {'OA_in':>6} {'OA_out':>7} {'GE_in':>6} {'GE_out':>7}")
        for r in rows:
            print(f"{r['name']:24} {r['chars']:>6} {r['oa_in']:>6} {r['oa_out']:>7} {r['ge_in']:>6} {r['ge_out']:>7}")

        def avg(k): return round(statistics.mean(r[k] for r in rows))
        def p90(k): return round(sorted(r[k] for r in rows)[int(len(rows) * 0.9) - 1])

        print(f"\nCVs medidos: {len(rows)}")
        print(f"EXTRACCIÓN promedio  → OpenAI: in={avg('oa_in')} out={avg('oa_out')} | Gemini: in={avg('ge_in')} out={avg('ge_out')}")
        print(f"EXTRACCIÓN p90       → OpenAI: in={p90('oa_in')} out={p90('oa_out')} | Gemini: in={p90('ge_in')} out={p90('ge_out')}")

        # ── Matching: prompts reales por candidato contra el job de prueba ──
        jobs = c.get(f"{API}/jobs", headers=HDR).json()["items"]
        job = next((j for j in jobs if "Cient" in j["title"]), jobs[0])
        m_in, m_out = [], []
        scores = c.get(f"{API}/jobs/{job['id']}/scores", headers=HDR).json().get("scores", [])
        out_by_id = {s["candidate_id"]: s for s in scores}
        for it in cands:
            d = c.get(f"{API}/candidates/{it['id']}", headers=HDR).json()
            if not d.get("skills"):
                continue
            p = render_prompt(
                "match_candidate_system") + "\n\n" + render_prompt(
                "match_candidate",
                job_title=job["title"],
                job_description=(job.get("description") or "")[:1500],
                required_skills=", ".join(job.get("required_skills") or []),
                preferred_skills=", ".join(job.get("preferred_skills") or []),
                min_experience_years=job.get("min_experience_years") or 0,
                candidate_skills=", ".join(d.get("skills") or []),
                experience_block=json.dumps(d.get("experience", []), ensure_ascii=False),
                education_block=json.dumps(d.get("education", []), ensure_ascii=False),
                languages_block=json.dumps(d.get("idiomas", []), ensure_ascii=False),
                candidate_summary=(d.get("summary") or "(no disponible)")[:800],
            )
            m_in.append(openai_count(p))
            s = out_by_id.get(it["id"])
            if s:
                m_out.append(openai_count(json.dumps({
                    "skills_score": s.get("skills_score"),
                    "experience_score": s.get("experience_score"),
                    "education_score": s.get("education_score"),
                    "relevant_experience_years": s.get("relevant_experience_years"),
                    "missing_critical_skills": s.get("missing_skills"),
                    "recommendation": s.get("recommendation"),
                    "explanation": s.get("explanation"),
                    "guia_entrevista": s.get("guia_entrevista"),
                }, ensure_ascii=False)))
        print(f"\nMATCHING ({len(m_in)} candidatos) → in promedio={round(statistics.mean(m_in))} "
              f"p90={sorted(m_in)[int(len(m_in)*0.9)-1]}")
        if m_out:
            print(f"MATCHING salida real ({len(m_out)} resultados) → out promedio={round(statistics.mean(m_out))}")


main()
