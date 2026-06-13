"""Eval task: matching candidato vs vacante.

Cada sample del dataset trae:
  - ``input``:  JSON serializado con la forma {candidate: {...}, job: {...}}
                donde candidato y vacante están YA estructurados (output ideal
                de los pasos anteriores — los aislamos para medir el matcher
                en sí, sin contaminación del extractor).
  - ``target``: JSON con expected_score (0-100), expected_recommendation,
                expected_missing_skills (lista).

El task llama a ``LLMEngine.reason_candidate_match()`` y mide:
  * Diferencia de score (normalizada)
  * Coincidencia de recomendación textual
  * F1 de missing_skills

Corre con:
    inspect eval evals/tasks/candidate_matching.py
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset

_DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "matching_golden.jsonl"


@task
def candidate_matching() -> Task:
    """Evalúa la calidad del matching candidato-vacante."""
    from evals.scorers.field_f1 import matching_alignment
    from evals.solvers.recruitai import matching_solver

    return Task(
        dataset=json_dataset(str(_DATASET_PATH)),
        solver=matching_solver(),
        scorer=matching_alignment(),
    )
