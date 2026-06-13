"""Eval task: extracción estructurada de CVs.

Cada sample del dataset trae:
  - ``input``:  texto del CV (markdown ya extraído por PyMuPDF4LLM o pegado a mano).
  - ``target``: JSON serializado con la extracción ESPERADA (ground truth).

El task llama a ``LLMEngine.extract_resume()`` (nuestro pipeline real) y mide
F1 por campo. Ejemplo de salida:

    cv_extraction (Llama 3.3 70B + strip_markdown_noise)
      nombre_completo:        F1 = 0.92
      email:                  F1 = 0.98
      experiencia_profesional F1 = 0.74    ← donde mejorar
      educacion:              F1 = 0.81
      weighted F1:            0.87

Corre con:
    inspect eval evals/tasks/cv_extraction.py
    inspect eval evals/tasks/cv_extraction.py --limit 5     # primeros 5
    inspect eval evals/tasks/cv_extraction.py --log-format json
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset

# Path absoluto al dataset golden (el archivo .jsonl)
_DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "cv_extraction_golden.jsonl"


@task
def cv_extraction() -> Task:
    """Evalúa nuestro pipeline de extracción de CVs sobre el dataset golden."""
    # Importes diferidos: solo se necesitan al ejecutar, no al listar tasks.
    from evals.scorers.field_f1 import cv_field_f1
    from evals.solvers.recruitai import extract_cv_solver

    return Task(
        dataset=json_dataset(str(_DATASET_PATH)),
        solver=extract_cv_solver(),
        scorer=cv_field_f1(),
    )
