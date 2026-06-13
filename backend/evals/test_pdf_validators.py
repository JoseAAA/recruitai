"""Tests de regresión del validador estructural de PDFs (upload safety).

Bug origen (2026-06-11): ``validate_pdf_bytes`` buscaba las claves peligrosas
(``/AA``, ``/JS``, …) como SUBCADENAS de cada objeto serializado. Las fuentes
embebidas con subset se llaman ``/AAAAAB+Calibri`` → contienen "/AA" → CVs
100% legítimos eran rechazados con "PDF rechazado: contiene /AA".

El arreglo busca las claves como claves reales de diccionario PDF. Estos tests
fijan ambos lados: los legítimos pasan, los maliciosos se siguen rechazando.

Ejecutar:
    docker exec recruitai-backend python -m pytest evals/test_pdf_validators.py -v
"""
import io

import pikepdf
import pytest

from app.core.validators import validate_pdf_bytes


def _pdf_bytes(pdf: pikepdf.Pdf) -> bytes:
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _blank_pdf() -> pikepdf.Pdf:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    return pdf


# ── Legítimos: deben PASAR ────────────────────────────────────────────────────

def test_pdf_simple_pasa():
    ok, reason = validate_pdf_bytes(_pdf_bytes(_blank_pdf()))
    assert ok, f"PDF en blanco rechazado: {reason}"


def test_fuente_subset_con_prefijo_AA_no_es_falso_positivo():
    """Una fuente subset ``/AAAAAB+Calibri`` contiene '/AA' como subcadena
    pero NO es un diccionario Additional-Actions. Antes se rechazaba."""
    pdf = _blank_pdf()
    font = pikepdf.Dictionary(
        Type=pikepdf.Name("/Font"),
        Subtype=pikepdf.Name("/TrueType"),
        BaseFont=pikepdf.Name("/AAAAAB+Calibri"),
    )
    pdf.pages[0]["/Resources"] = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(F1=pdf.make_indirect(font))
    )
    ok, reason = validate_pdf_bytes(_pdf_bytes(pdf))
    assert ok, f"Falso positivo con fuente subset: {reason}"


def test_texto_con_slash_aa_en_contenido_no_es_falso_positivo():
    """Una cadena de texto con '/AA' dentro (p.ej. una URL o código) no debe
    disparar el rechazo: solo cuentan las CLAVES de diccionario."""
    pdf = _blank_pdf()
    pdf.Root["/Lang"] = pikepdf.String("es-PE /AA /JS dummy")
    ok, reason = validate_pdf_bytes(_pdf_bytes(pdf))
    assert ok, f"Falso positivo con string de contenido: {reason}"


# ── Maliciosos: deben RECHAZARSE ─────────────────────────────────────────────

def test_openaction_javascript_se_rechaza():
    pdf = _blank_pdf()
    js = pikepdf.Dictionary(S=pikepdf.Name("/JavaScript"), JS="app.alert(1)")
    pdf.Root["/OpenAction"] = pdf.make_indirect(js)
    ok, reason = validate_pdf_bytes(_pdf_bytes(pdf))
    assert not ok
    assert "/OpenAction" in (reason or "")


def test_aa_real_en_pagina_se_rechaza():
    """Un /AA real (additional actions al abrir la página) sí es vector de
    ataque y debe seguir bloqueado tras el arreglo del falso positivo."""
    pdf = _blank_pdf()
    pdf.pages[0]["/AA"] = pikepdf.Dictionary(
        O=pikepdf.Dictionary(S=pikepdf.Name("/JavaScript"), JS="x")
    )
    ok, reason = validate_pdf_bytes(_pdf_bytes(pdf))
    assert not ok
    assert "/AA" in (reason or "")


def test_aa_anidado_en_dict_directo_se_rechaza():
    """/AA dentro de un diccionario directo anidado (no objeto indirecto)
    también debe detectarse — el scan es recursivo."""
    pdf = _blank_pdf()
    pdf.pages[0]["/Wrapper"] = pikepdf.Dictionary(
        Inner=pikepdf.Dictionary(AA=pikepdf.Dictionary(O=pikepdf.Name("/X")))
    )
    ok, reason = validate_pdf_bytes(_pdf_bytes(pdf))
    assert not ok


def test_no_pdf_se_rechaza():
    ok, reason = validate_pdf_bytes(b"MZ\x90\x00 esto no es un pdf" * 10)
    assert not ok


def test_pdf_truncado_se_rechaza():
    contenido = _pdf_bytes(_blank_pdf())
    ok, reason = validate_pdf_bytes(contenido[: len(contenido) // 3])
    assert not ok
