"""Eval task: extracción estructurada de perfiles de puesto.

Mismo patrón que cv_extraction.py pero contra el extractor de vacantes.

Corre con:
    inspect eval evals/tasks/job_profile_extraction.py
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset

_DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "job_profile_golden.jsonl"


@task
def job_profile_extraction() -> Task:
    """Evalúa el pipeline de extracción de perfiles de puesto."""
    from evals.scorers.field_f1 import job_field_f1
    from evals.solvers.recruitai import extract_job_profile_solver

    return Task(
        dataset=json_dataset(str(_DATASET_PATH)),
        solver=extract_job_profile_solver(),
        scorer=job_field_f1(),
    )
