"""Tests de regresión deterministas para el pipeline de extracción/validación.

Cada test reproduce un bug real encontrado en la auditoría 2026-06-07 y verifica
que la corrección lo previene. A diferencia de los evals de Inspect AI (que miden
la calidad de extracción del LLM end-to-end y necesitan el modelo corriendo),
estos tests son **deterministas**: ejercitan los validadores Pydantic y el
post-proceso del ``LLMEngine`` con las salidas malformadas exactas que el LLM
(sobre todo en modo cloud) produce, sin invocar ningún modelo.

Correr (con el container backend levantado):

    docker exec recruitai-backend pytest evals/test_extraction_robustness.py -v

Mapa bug → test:
  C1  fecha de experiencia numérica          → test_experiencia_fecha_numerica_*
  C2  resumen_logros como string/número       → test_resumen_logros_*
  C3  min_experience_years '3-5 años'         → test_min_experience_years_*
  C4  habilidades como string                 → test_required_skills_*, test_habilidades_cv_*
  H4  certificación con tilde / diplomado     → test_normalize_tipo_*
  H8  nivel de idioma numérico                → test_idioma_requerido_nivel_*
  H1  cargo/empresa partido en renglones      → test_guardia_no_borra_experiencia_partida
  H2  cargo/empresa con tildes/ñ en NFD        → test_guardia_no_borra_experiencia_nfd
  H5  educación duplicada por título           → test_dedup_educacion_*

Nota: H3 (scores no numéricos del match) y H7 (prompt pide los logros) son
end-to-end y se verifican corriendo los evals de Inspect AI con un modelo.
"""
from __future__ import annotations

import unicodedata

import pytest

from app.domain.models import (
    DatosPersonales,
    EducacionProfesional,
    ExperienciaProfesional,
    ExtractedJobProfile,
    ExtractedResume,
    IdiomaRequerido,
)


# ─────────────────────────── C1: fechas numéricas ───────────────────────────

def test_experiencia_fecha_numerica_se_coacciona_a_str():
    """C1: un año como entero (2020) no debe lanzar ValidationError."""
    exp = ExperienciaProfesional(
        cargo="Analista", empresa="Acme", fecha_inicio=2020, fecha_fin=2023
    )
    assert exp.fecha_inicio == "2020"
    assert exp.fecha_fin == "2023"


def test_experiencia_fecha_numerica_no_tira_todo_el_cv():
    """C1: el CV completo debe construirse aunque una fecha venga como int."""
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Juan Pérez"),
        experiencia_profesional=[
            {"cargo": "Analista", "empresa": "Acme", "fecha_inicio": 2020, "fecha_fin": 2023}
        ],
    )
    assert resume.experiencia_profesional[0].fecha_inicio == "2020"


# ─────────────────────────── C2: resumen_logros ─────────────────────────────

def test_resumen_logros_string_se_envuelve_en_lista():
    """C2: un logro emitido como string suelto se convierte en lista."""
    exp = ExperienciaProfesional(cargo="X", empresa="Y", resumen_logros="Aumenté ventas 20%")
    assert exp.resumen_logros == ["Aumenté ventas 20%"]


def test_resumen_logros_lista_con_numeros_y_nulos():
    """C2: items no-string (números) y nulos no deben romper el CV."""
    exp = ExperienciaProfesional(
        cargo="X", empresa="Y", resumen_logros=["Lideré equipo", 95, None, "  "]
    )
    assert exp.resumen_logros == ["Lideré equipo", "95"]


def test_resumen_logros_none_es_lista_vacia():
    exp = ExperienciaProfesional(cargo="X", empresa="Y", resumen_logros=None)
    assert exp.resumen_logros == []


# ───────────────────── C3: min_experience_years coerción ────────────────────

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("3-5 años", 3),
        ("de 3 a 5 años", 3),
        ("5+", 5),
        ("mínimo 5 años", 5),
        ("+5 años de experiencia", 5),
        ("5", 5),
        (5, 5),
        (4.5, 4),
        (None, 0),
        ("", 0),
        ("no especificado", 0),
        (True, 0),  # bool no debe colarse como 1
    ],
)
def test_min_experience_years_coercion(entrada, esperado):
    """C3: frases reales del LLM no deben tumbar la importación de la vacante."""
    job = ExtractedJobProfile(title="Dev", min_experience_years=entrada)
    assert job.min_experience_years == esperado


# ─────────────────── C4: habilidades como string (vacante y CV) ─────────────

def test_required_skills_string_no_se_parte_letra_por_letra():
    """C4: 'Python, SQL, Excel' debe dar 3 skills, no 11 caracteres."""
    job = ExtractedJobProfile(title="Dev", required_skills="Python, SQL, Excel")
    assert job.required_skills == ["Python", "SQL", "Excel"]


def test_preferred_skills_none_es_lista_vacia():
    job = ExtractedJobProfile(title="Dev", preferred_skills=None)
    assert job.preferred_skills == []


def test_habilidades_cv_string_no_se_pierden():
    """C4 (gemelo CV): habilidades como string no deben descartarse en silencio."""
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Juan"),
        habilidades="Python, SQL, Excel",
    )
    assert set(resume.habilidades) == {"Python", "SQL", "Excel"}


# ─────────────────────── H4: clasificación de certificaciones ───────────────

@pytest.mark.parametrize(
    "tipo_in,esperado",
    [
        ("certificación", "certificacion"),  # ortografía correcta con tilde
        ("certificacion", "certificacion"),
        ("Certification", "certificacion"),
        ("diplomado", "certificacion"),
        ("Diplomado", "certificacion"),
        ("curso", "certificacion"),
        ("bootcamp", "certificacion"),
        ("educacion", "educacion"),
        ("universitario", "educacion"),
        ("", "educacion"),
    ],
)
def test_normalize_tipo_reconoce_certificaciones(tipo_in, esperado):
    """H4: 'certificación'/'diplomado'/'curso' no deben caer como educación formal."""
    edu = EducacionProfesional(institucion="X", titulo="Y", tipo=tipo_in)
    assert edu.tipo == esperado


# ─────────────────────── H8: nivel de idioma numérico ───────────────────────

def test_idioma_requerido_nivel_numerico_no_rompe_vacante():
    """H8: un nivel emitido como número no debe tirar la extracción de la vacante."""
    lang = IdiomaRequerido(idioma="Inglés", nivel=2)
    assert lang.nivel == "2"
    job = ExtractedJobProfile(
        title="Dev", required_languages=[{"idioma": "Inglés", "nivel": 2}]
    )
    assert job.required_languages[0].nivel == "2"


# ───────── H1/H2/H5: post-proceso del LLMEngine (sin invocar el modelo) ──────

@pytest.fixture(scope="module")
def engine():
    # __init__ solo asigna atributos a None; el provider se carga lazy, así que
    # esto NO hace red ni necesita Ollama/cloud.
    from app.adapters.llm_engine import LLMEngine

    return LLMEngine(enable_pii_masking=False)


def _resume_con_experiencia(cargo: str, empresa: str) -> ExtractedResume:
    return ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Juan Pérez"),
        experiencia_profesional=[ExperienciaProfesional(cargo=cargo, empresa=empresa)],
    )


def test_guardia_no_borra_experiencia_partida_en_renglones(engine):
    """H1: cargo/empresa partidos por saltos de línea en el PDF deben sobrevivir."""
    resume = _resume_con_experiencia("Jefe de Operaciones Logísticas", "Corporación Backus")
    raw_text = (
        "EXPERIENCIA PROFESIONAL\n"
        "Jefe de Operaciones\nLogísticas\n"
        "Corporación\nBackus\n"
        "Enero 2020 - Presente\n"
    )
    out = engine._normalize_extracted_resume(resume, raw_text)
    assert len(out.experiencia_profesional) == 1, "se borró una experiencia real"
    assert out.experiencia_profesional[0].cargo, "el cargo se vació por falso positivo"


def test_guardia_no_borra_experiencia_nfd(engine):
    """H2: acentos descompuestos (NFD) en el PDF no deben borrar la experiencia."""
    resume = _resume_con_experiencia("Ingeniería de Sistemas", "Compañía Minera del Perú")
    raw_text = unicodedata.normalize(
        "NFD",
        "EXPERIENCIA\nIngeniería de Sistemas en Compañía Minera del Perú\n2019 - 2022\n",
    )
    out = engine._normalize_extracted_resume(resume, raw_text)
    assert len(out.experiencia_profesional) == 1, "se borró experiencia con tildes/ñ (NFD)"
    assert out.experiencia_profesional[0].empresa, "la empresa se vació por NFC vs NFD"


def test_dedup_educacion_conserva_instituciones_distintas(engine):
    """H5: el mismo diplomado en dos centros NO debe colapsar en uno."""
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Juan"),
        educacion=[
            EducacionProfesional(
                institucion="PUCP", titulo="Diplomado en Gestión de Proyectos", tipo="certificacion"
            ),
            EducacionProfesional(
                institucion="ESAN", titulo="Diplomado en Gestión de Proyectos", tipo="certificacion"
            ),
        ],
    )
    raw_text = (
        "FORMACIÓN\nDiplomado en Gestión de Proyectos - PUCP\n"
        "Diplomado en Gestión de Proyectos - ESAN\n"
    )
    out = engine._normalize_extracted_resume(resume, raw_text)
    assert len(out.educacion) == 2, "se perdió una credencial de una institución distinta"


# ───────────────────── medium/low: datos fabricados / inconsistencias ───────

def test_idioma_requerido_omitido_no_es_obligatorio():
    """D: un idioma sin marca explícita de obligatorio NO debe sobre-filtrar."""
    lang = IdiomaRequerido(idioma="Inglés", nivel="Intermedio")
    assert lang.obligatorio is False


def test_coerce_idioma_sin_nivel_no_inventa_intermedio(engine):
    """A: un idioma listado sin nivel debe quedar '' (no 'Intermedio' inventado)."""
    parsed = engine._coerce_resume_shape(
        {"datos_personales": {"nombre_completo": "Juan"}, "idiomas": ["Inglés"]}
    )
    assert parsed["idiomas"][0]["idioma"] == "Inglés"
    assert parsed["idiomas"][0]["nivel"] == ""


def test_dedup_no_colapsa_ascensos_misma_empresa(engine):
    """B: dos cargos distintos en la misma empresa/fecha son un ascenso, no un duplicado."""
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Juan"),
        experiencia_profesional=[
            ExperienciaProfesional(cargo="Analista de Riesgos", empresa="BCP", fecha_inicio="2018-01"),
            ExperienciaProfesional(cargo="Jefe de Proyectos", empresa="BCP", fecha_inicio="2018-01"),
        ],
    )
    raw_text = (
        "EXPERIENCIA\nAnalista de Riesgos en BCP 2018\n"
        "Jefe de Proyectos en BCP 2018\n"
    )
    out = engine._normalize_extracted_resume(resume, raw_text)
    assert len(out.experiencia_profesional) == 2, "se colapsó un ascenso legítimo"


def test_guardia_no_borra_ascensos_empresa_unica(engine):
    """Bug CV real (Alexander, 2026-06-12): empresa UNA vez como título +
    4 cargos debajo (formato ascensos). Los cargos antiguos quedan a >800
    chars de la empresa y el guardia de distancia los borraba — quedaba
    solo el cargo actual (3.5 años en vez de 6.5)."""
    relleno = "Logros y responsabilidades del puesto. " * 30  # ~1170 chars
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Alexander"),
        experiencia_profesional=[
            ExperienciaProfesional(cargo="Lean Agile Coach", empresa="Danper Trujillo", fecha_inicio="2022-12"),
            ExperienciaProfesional(cargo="Gestor de Mejora de Procesos", empresa="Danper Trujillo", fecha_inicio="2019-12"),
        ],
    )
    raw_text = (
        "EXPERIENCIA LABORAL\nDanper Trujillo\n"
        f"Lean Agile Coach\nDic 2022 - Presente\n{relleno}\n"
        "Gestor de Mejora de Procesos\nDic 2019 - Feb 2021\n"
    )
    out = engine._normalize_extracted_resume(resume, raw_text)
    assert len(out.experiencia_profesional) == 2, (
        "el guardia de distancia borró un ascenso legítimo (empresa única + cargos lejos)"
    )


def test_guardia_si_borra_fusion_cross_block(engine):
    """La detección de fusión real debe seguir activa: cargo pegado a la
    empresa A pero emparejado con la empresa B (lejana) = alucinación."""
    relleno = "Texto intermedio de otro bloque del CV. " * 30
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="Juan"),
        experiencia_profesional=[
            # El LLM fusionó: el cargo aparece junto a "Alicorp" en el texto,
            # pero lo emparejó con "Backus" que está a >800 chars.
            ExperienciaProfesional(cargo="Analista de Calidad", empresa="Backus", fecha_inicio="2020-01"),
            ExperienciaProfesional(cargo="Supervisor de Planta", empresa="Alicorp", fecha_inicio="2018-01"),
        ],
    )
    raw_text = (
        "EXPERIENCIA\nAlicorp\nAnalista de Calidad\n2020\n"
        "Supervisor de Planta\n2018\n"
        f"{relleno}\nBackus\nOtro puesto antiguo\n2015\n"
    )
    out = engine._normalize_extracted_resume(resume, raw_text)
    cargos = [e.cargo for e in out.experiencia_profesional]
    assert "Analista de Calidad" not in cargos, (
        "la fusión cross-block (otra empresa más cercana al cargo) debió borrarse"
    )


def test_nombre_conserva_particulas_hispanas(engine):
    """C: 'de la Cruz' no debe romperse a 'De La Cruz' en el post-proceso."""
    resume = ExtractedResume(
        datos_personales=DatosPersonales(nombre_completo="JUAN CARLOS DE LA CRUZ"),
    )
    out = engine._normalize_extracted_resume(resume, "")
    nombre = out.datos_personales.nombre_completo
    assert "De La Cruz" not in nombre, f"se rompieron las partículas: {nombre!r}"
    assert "de la Cruz" in nombre, f"no se conservó la partícula: {nombre!r}"


# ───────────────────── lectura PDF: re-armado de fragmentos ──────────────────

def test_email_fragmentado_no_fabrica_de_palabra_previa():
    """G: 'Ana Torres - @empresa.com' NO debe convertirse en 'Torres@empresa.com'."""
    from app.adapters.document_extractor import _join_fragmented_emails

    # Palabra suelta (un apellido) antes del @ → NO se sintetiza un email.
    out = _join_fragmented_emails("Ana Torres - @empresa.com")
    assert "Torres@empresa.com" not in out
    # Un local-part real (con punto) sí se re-une cuando lo parte un ícono.
    out2 = _join_fragmented_emails("ana.torres ° @gmail.com")
    assert "ana.torres@gmail.com" in out2


def test_url_perfil_no_pega_encabezado_de_seccion():
    """H: 'linkedin.com/in/' + 'EXPERIENCIA' NO debe formar un perfil falso."""
    from app.adapters.document_extractor import _join_split_profile_urls

    out = _join_split_profile_urls("linkedin.com/in/\nEXPERIENCIA")
    assert "/in/EXPERIENCIA" not in out  # no se pegó el encabezado
    # Un handle real sí se re-une.
    out2 = _join_split_profile_urls("linkedin.com/in/\njuanperez")
    assert "linkedin.com/in/juanperez" in out2
