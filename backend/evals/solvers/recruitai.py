"""Solvers de Inspect AI que invocan nuestras funciones REALES de LLMEngine.

¿Por qué un solver custom en vez de ``inspect.solver.generate()``?
==================================================================

``generate()`` de Inspect llama al modelo directamente con un prompt simple,
pero nuestro pipeline tiene capas: PII masking, ``_strip_markdown_noise``,
prompt curado, defensive unwrap, fallback de title, normalización con
``_normalize_extracted_resume``, etc. Si medimos solo el LLM en aislado,
los números no representan el sistema que el cliente realmente usa.

Estos solvers son delgados envoltorios sobre ``LLMEngine.extract_resume()``,
``extract_job_profile()`` y ``reason_candidate_match()`` que graban la salida
en ``TaskState.metadata`` para que el scorer luego la compare contra el
ground truth.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from inspect_ai.solver import Generate, Solver, TaskState, solver

# Importes deferidos en cada solver para que ``inspect eval --help`` no
# importe el adapter LLM en frío (requiere DB y otros initializers).


@solver
def extract_cv_solver() -> Solver:
    """Solver: input = texto del CV, output = JSON extraído por nuestro LLM.

    El dataset debe traer cada sample con ``input`` = texto del CV (markdown
    ya extraído por PyMuPDF4LLM/MarkItDown). El solver llama a
    ``LLMEngine.extract_resume()`` y guarda el dict JSON en
    ``state.metadata["prediction"]``.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        from app.adapters.llm_engine import LLMEngine

        llm = LLMEngine()
        cv_text = state.input_text
        try:
            extracted = await llm.extract_resume(cv_text)
            state.metadata["prediction"] = extracted.model_dump()
            state.metadata["error"] = None
            state.output.completion = json.dumps(
                extracted.model_dump(), ensure_ascii=False
            )
        except Exception as exc:  # pragma: no cover — defensive
            state.metadata["prediction"] = None
            state.metadata["error"] = f"{type(exc).__name__}: {exc}"
            state.output.completion = ""
        return state

    return solve


@solver
def extract_job_profile_solver() -> Solver:
    """Solver: input = texto del perfil de puesto, output = JSON extraído."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        from app.adapters.llm_engine import LLMEngine

        llm = LLMEngine()
        job_text = state.input_text
        try:
            extracted = await llm.extract_job_profile(job_text)
            state.metadata["prediction"] = extracted.model_dump()
            state.metadata["error"] = None
            state.output.completion = json.dumps(
                extracted.model_dump(), ensure_ascii=False
            )
        except Exception as exc:  # pragma: no cover
            state.metadata["prediction"] = None
            state.metadata["error"] = f"{type(exc).__name__}: {exc}"
            state.output.completion = ""
        return state

    return solve


@solver
def matching_solver() -> Solver:
    """Solver: input = JSON con {candidate, job}, output = scores del matcher.

    Cada sample del dataset trae:
      input  = JSON {candidate: {...}, job: {...}}
      target = JSON {expected_score, expected_recommendation, ...}
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        from app.adapters.llm_engine import LLMEngine

        llm = LLMEngine()
        payload: dict[str, Any] = json.loads(state.input_text)
        cand = payload["candidate"]
        job = payload["job"]

        try:
            reasoning = await llm.reason_candidate_match(
                candidate_skills=cand.get("skills") or [],
                job_title=job.get("title") or "",
                job_description=job.get("description") or "",
                required_skills=job.get("required_skills") or [],
                preferred_skills=job.get("preferred_skills") or [],
                min_experience_years=job.get("min_experience_years") or 0,
                candidate_experience=cand.get("experience") or [],
                candidate_education=cand.get("education") or [],
                candidate_languages=cand.get("languages") or None,
                candidate_summary=cand.get("summary"),
            )
            state.metadata["prediction"] = reasoning
            state.metadata["error"] = None
            state.output.completion = json.dumps(reasoning, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover
            state.metadata["prediction"] = None
            state.metadata["error"] = f"{type(exc).__name__}: {exc}"
            state.output.completion = ""
        return state

    return solve
