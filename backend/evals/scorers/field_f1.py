"""Scorer field-level F1 para extracción estructurada (CVs y perfiles).

El "pass/fail" general no nos sirve: necesitamos saber DÓNDE falla el LLM
(nombre vs experiencias vs educación) para priorizar el siguiente fix.

Estrategias de comparación por tipo de campo:

  * **exact**     — match exacto (case-insensitive, trim). Para emails,
                    teléfonos normalizados, niveles de educación, modalidades.
  * **fuzzy**     — similitud de cadenas (rapidfuzz). Para nombres, empresas,
                    instituciones, cargos, títulos académicos. Umbral 85.
  * **set**       — intersección de conjuntos. Para skills, idiomas.
  * **list_dict** — lista de objetos. Compara por clave-pivote (ej: empresa)
                    y dentro de cada match calcula sub-F1 por campo.

Métrica final por campo:
  precision = #aciertos / #valores predichos
  recall    = #aciertos / #valores esperados
  F1        = 2 * P * R / (P + R)

Métrica agregada del eval:
  ``weighted_f1`` = promedio de F1 ponderado por importancia de campo.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState
from rapidfuzz import fuzz


# ─── Helpers genéricos ──────────────────────────────────────────────────────

def _norm(s: Any) -> str:
    """Normaliza string para comparación: lower + colapso de espacios."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _safe_get(obj: dict | None, path: str, default: Any = None) -> Any:
    """Acceso seguro por dot-path: ``_safe_get(d, "datos_personales.email")``."""
    if obj is None:
        return default
    cur: Any = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


# ─── Comparadores ───────────────────────────────────────────────────────────

def _cmp_exact(pred: Any, gold: Any) -> tuple[int, int, int]:
    """Devuelve (TP, FP, FN). Para campos string simples.

    - TP: ambos no vacíos y normalizados iguales.
    - FP: predicción no vacía pero no coincide con gold.
    - FN: gold no vacío y la predicción no coincide.
    Si ambos vacíos → (0, 0, 0) (no penaliza).
    """
    p, g = _norm(pred), _norm(gold)
    if not p and not g:
        return 0, 0, 0
    if p == g:
        return 1, 0, 0
    if p and not g:
        return 0, 1, 0
    if g and not p:
        return 0, 0, 1
    return 0, 1, 1  # ambos presentes y distintos


def _cmp_fuzzy(pred: Any, gold: Any, threshold: int = 85) -> tuple[int, int, int]:
    """Como exact pero acepta similitud >= threshold (rapidfuzz token_set_ratio)."""
    p, g = _norm(pred), _norm(gold)
    if not p and not g:
        return 0, 0, 0
    if not p:
        return 0, 0, 1
    if not g:
        return 0, 1, 0
    if fuzz.token_set_ratio(p, g) >= threshold:
        return 1, 0, 0
    return 0, 1, 1


def _cmp_set(
    pred: Iterable[Any] | None,
    gold: Iterable[Any] | None,
    fuzzy_threshold: int = 88,
) -> tuple[int, int, int]:
    """Compara listas como conjuntos con fuzzy matching opcional.

    Útil para skills, idiomas. Cada item del gold se intenta matchear con un
    item del pred (no consumido aún) por similitud. Cada match consume ambos.
    """
    pred_list = [_norm(x) for x in (pred or []) if _norm(x)]
    gold_list = [_norm(x) for x in (gold or []) if _norm(x)]
    if not pred_list and not gold_list:
        return 0, 0, 0

    matched_pred_idx: set[int] = set()
    tp = 0
    for g in gold_list:
        best_idx, best_score = -1, 0
        for i, p in enumerate(pred_list):
            if i in matched_pred_idx:
                continue
            score = fuzz.token_set_ratio(p, g)
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx >= 0 and best_score >= fuzzy_threshold:
            matched_pred_idx.add(best_idx)
            tp += 1
    fp = len(pred_list) - tp
    fn = len(gold_list) - tp
    return tp, fp, fn


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0 and fp == 0 and fn == 0:
        return 1.0  # campo opcional ausente en ambos lados — no penaliza
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ─── Specs de campos por tipo de documento ─────────────────────────────────

# Cada entrada: (path_en_objeto, modo, peso)
# Pesos: campos críticos = 3, secundarios = 1.

CV_FIELDS = [
    # críticos (peso 3) — afectan el matching directamente
    ("datos_personales.nombre_completo", "fuzzy", 3),
    ("datos_personales.email", "exact", 3),
    ("habilidades", "set", 3),
    ("experiencia_profesional", "list_experience", 3),
    ("educacion", "list_education", 3),
    # secundarios (peso 1)
    ("datos_personales.telefono", "exact", 1),
    ("datos_personales.linkedin", "exact", 1),
    ("resumen_profesional", "presence", 1),
    ("idiomas", "list_languages", 1),
]

JOB_FIELDS = [
    ("title", "fuzzy", 3),
    ("required_skills", "set", 3),
    ("min_experience_years", "exact", 3),
    ("education_level", "exact", 3),
    ("preferred_skills", "set", 1),
    ("department", "fuzzy", 1),
    ("seniority_level", "exact", 1),
    ("work_modality", "exact", 1),
    ("location", "fuzzy", 1),
    ("responsibilities", "set", 1),
    ("required_languages", "list_languages", 1),
]


# ─── Comparadores especializados ───────────────────────────────────────────

def _cmp_list_experience(pred: list | None, gold: list | None) -> tuple[int, int, int]:
    """Compara experiencias profesionales matcheando por (empresa fuzzy)."""
    pred = pred or []
    gold = gold or []
    if not pred and not gold:
        return 0, 0, 0

    matched_pred: set[int] = set()
    tp = 0
    for g in gold:
        g_empresa = _norm(g.get("empresa"))
        best_idx, best_score = -1, 0
        for i, p in enumerate(pred):
            if i in matched_pred:
                continue
            p_empresa = _norm(p.get("empresa"))
            if not g_empresa or not p_empresa:
                continue
            score = fuzz.token_set_ratio(g_empresa, p_empresa)
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx >= 0 and best_score >= 80:
            # verificar también que el cargo se parezca razonablemente
            g_cargo = _norm(g.get("cargo"))
            p_cargo = _norm(pred[best_idx].get("cargo"))
            if not g_cargo or fuzz.token_set_ratio(g_cargo, p_cargo) >= 70:
                matched_pred.add(best_idx)
                tp += 1
    fp = len(pred) - tp
    fn = len(gold) - tp
    return tp, fp, fn


def _cmp_list_education(pred: list | None, gold: list | None) -> tuple[int, int, int]:
    """Compara educación matcheando por (institución fuzzy)."""
    pred = pred or []
    gold = gold or []
    if not pred and not gold:
        return 0, 0, 0

    matched_pred: set[int] = set()
    tp = 0
    for g in gold:
        g_inst = _norm(g.get("institucion"))
        best_idx, best_score = -1, 0
        for i, p in enumerate(pred):
            if i in matched_pred:
                continue
            p_inst = _norm(p.get("institucion"))
            if not g_inst or not p_inst:
                continue
            score = fuzz.token_set_ratio(g_inst, p_inst)
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx >= 0 and best_score >= 75:
            matched_pred.add(best_idx)
            tp += 1
    fp = len(pred) - tp
    fn = len(gold) - tp
    return tp, fp, fn


def _cmp_list_languages(pred: list | None, gold: list | None) -> tuple[int, int, int]:
    """Compara listas de idiomas por nombre del idioma."""
    pred_names = [_norm(x.get("idioma") if isinstance(x, dict) else x) for x in (pred or [])]
    gold_names = [_norm(x.get("idioma") if isinstance(x, dict) else x) for x in (gold or [])]
    return _cmp_set(pred_names, gold_names, fuzzy_threshold=90)


def _cmp_presence(pred: Any, gold: Any) -> tuple[int, int, int]:
    """Solo verifica que si gold tiene contenido, pred también."""
    p = bool(_norm(pred))
    g = bool(_norm(gold))
    if p and g:
        return 1, 0, 0
    if p and not g:
        return 0, 1, 0
    if g and not p:
        return 0, 0, 1
    return 0, 0, 0


_COMPARATORS = {
    "exact": _cmp_exact,
    "fuzzy": _cmp_fuzzy,
    "set": _cmp_set,
    "list_experience": _cmp_list_experience,
    "list_education": _cmp_list_education,
    "list_languages": _cmp_list_languages,
    "presence": _cmp_presence,
}


def _evaluate_fields(prediction: dict, gold: dict, field_specs: list) -> dict:
    """Calcula F1 por campo y weighted F1 global. Devuelve dict con métricas."""
    per_field: dict[str, float] = {}
    weighted_sum = 0.0
    weight_total = 0.0
    for path, mode, weight in field_specs:
        cmp_fn = _COMPARATORS[mode]
        pred_val = _safe_get(prediction, path)
        gold_val = _safe_get(gold, path)
        tp, fp, fn = cmp_fn(pred_val, gold_val)
        f1 = _f1(tp, fp, fn)
        per_field[path] = round(f1, 3)
        weighted_sum += f1 * weight
        weight_total += weight
    weighted_f1 = round(weighted_sum / weight_total, 3) if weight_total else 0.0
    return {"weighted_f1": weighted_f1, "per_field": per_field}


# ─── Scorers públicos (Inspect AI) ─────────────────────────────────────────

def _parse_gold(target: Target) -> dict | None:
    """Target en Inspect llega como string; lo parseamos a dict si es JSON."""
    text = target.text if hasattr(target, "text") else str(target)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


@scorer(metrics=[mean()])
def cv_field_f1() -> Scorer:
    """Scorer F1 por campo para extracción de CVs."""

    async def score(state: TaskState, target: Target) -> Score:
        pred = state.metadata.get("prediction")
        gold = _parse_gold(target)
        if pred is None or gold is None:
            err = state.metadata.get("error") or "missing prediction or target"
            return Score(value=0.0, explanation=f"eval failed: {err}")
        report = _evaluate_fields(pred, gold, CV_FIELDS)
        return Score(
            value=report["weighted_f1"],
            answer=json.dumps(pred, ensure_ascii=False)[:500],
            explanation=json.dumps(report["per_field"], ensure_ascii=False, indent=2),
            metadata=report,
        )

    return score


@scorer(metrics=[mean()])
def job_field_f1() -> Scorer:
    """Scorer F1 por campo para extracción de perfiles de puesto."""

    async def score(state: TaskState, target: Target) -> Score:
        pred = state.metadata.get("prediction")
        gold = _parse_gold(target)
        if pred is None or gold is None:
            err = state.metadata.get("error") or "missing prediction or target"
            return Score(value=0.0, explanation=f"eval failed: {err}")
        report = _evaluate_fields(pred, gold, JOB_FIELDS)
        return Score(
            value=report["weighted_f1"],
            answer=json.dumps(pred, ensure_ascii=False)[:500],
            explanation=json.dumps(report["per_field"], ensure_ascii=False, indent=2),
            metadata=report,
        )

    return score


@scorer(metrics=[mean()])
def matching_alignment() -> Scorer:
    """Scorer para matching candidato-vacante.

    Mide tres cosas:
      1. ``score_diff``: diferencia absoluta entre score predicho y esperado,
         normalizada (1.0 = exacto, 0.0 = diferencia >= 50 puntos).
      2. ``recommendation_match``: 1.0 si coincide la categoría textual
         (Altamente recomendado / Buena opción / Considerar / No recomendado).
      3. ``missing_skills_set``: F1 de skills faltantes detectadas vs golden.
    El valor agregado es el promedio ponderado.
    """

    async def score(state: TaskState, target: Target) -> Score:
        pred = state.metadata.get("prediction")
        gold = _parse_gold(target)
        if pred is None or gold is None:
            err = state.metadata.get("error") or "missing prediction or target"
            return Score(value=0.0, explanation=f"eval failed: {err}")

        pred_score = float(pred.get("overall_score") or pred.get("skills_score") or 0)
        # En el solver actual ``reason_candidate_match`` devuelve dimensiones,
        # no overall_score. Calculamos overall si no vino.
        if "overall_score" not in pred:
            s = pred.get("skills_score") or 0
            e = pred.get("experience_score") or 0
            ed = pred.get("education_score") or 0
            pred_score = round(s * 0.4 + e * 0.35 + ed * 0.25, 1)

        gold_score = float(gold.get("expected_score") or 0)
        diff = abs(pred_score - gold_score)
        # Normalizar: 1.0 si diff=0, 0.0 si diff>=50
        score_diff_norm = max(0.0, 1.0 - diff / 50.0)

        # Recomendación textual
        pred_rec = _norm(pred.get("recommendation"))
        gold_rec = _norm(gold.get("expected_recommendation"))
        rec_match = 1.0 if pred_rec and pred_rec == gold_rec else 0.0

        # Missing skills F1
        tp, fp, fn = _cmp_set(
            pred.get("missing_skills") or [],
            gold.get("expected_missing_skills") or [],
        )
        missing_f1 = _f1(tp, fp, fn)

        # Promedio ponderado: score=0.5, rec=0.3, missing_skills=0.2
        overall = round(score_diff_norm * 0.5 + rec_match * 0.3 + missing_f1 * 0.2, 3)

        report = {
            "pred_overall_score": pred_score,
            "gold_overall_score": gold_score,
            "score_diff": diff,
            "score_diff_norm": round(score_diff_norm, 3),
            "recommendation_match": rec_match,
            "missing_skills_f1": round(missing_f1, 3),
            "overall": overall,
        }
        return Score(
            value=overall,
            answer=json.dumps(pred, ensure_ascii=False)[:300],
            explanation=json.dumps(report, ensure_ascii=False, indent=2),
            metadata=report,
        )

    return score
