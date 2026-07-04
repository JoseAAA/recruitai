Evalúa qué tan bien encaja ESTE candidato en la vacante mediante COMPARACIÓN SEMÁNTICA (significado contra significado, no palabras contra palabras) y devuelve UN SOLO JSON con la forma exacta indicada. Eres exigente y honesto: un puntaje alto se gana, no se regala.

PROCEDIMIENTO OBLIGATORIO (síguelo en este orden):

PASO 1 — EMPAREJAMIENTO SEMÁNTICO. Para CADA habilidad REQUERIDA, decide a cuál de estos cuatro casos corresponde el candidato, citando la evidencia del CV:
  • CUBIERTA: la domina con evidencia de uso real (la misma habilidad, un sinónimo o una tecnología equivalente de la misma familia).
  • PARCIAL: tiene algo transferible o adyacente, pero no equivalente pleno.
  • AUSENTE: no hay evidencia de la habilidad ni de un equivalente.
  Repite el mismo razonamiento para las DESEABLES (suman, no restan).

PASO 2 — Escribe "_razonamiento_previo" resumiendo el emparejamiento: cuántas requeridas quedaron CUBIERTAS / PARCIALES / AUSENTES, cuántos años tiene en funciones afines (nombrando los roles) y si su formación pertenece a la disciplina central del puesto.

PASO 3 — Asigna los puntajes DESPUÉS, coherentes con el emparejamiento, usando las BANDAS ANCLADAS de abajo.

ESCALA ANCLADA (vale para skills_score, experience_score y education_score; entero de 0 a 100):
  • 90–100 — Excepcional: cubriría el rol sin brecha desde el día uno. Raro.
  • 75–89  — Fuerte: cubre la gran mayoría con solidez; brechas menores y subsanables.
  • 60–74  — Adecuado: cubre el núcleo pero con brechas claras que requieren ramp-up.
  • 40–59  — Débil: cubre solo una minoría del núcleo; brechas importantes.
  • 20–39  — Marginal: mayormente fuera del perfil; solo coincidencias tangenciales.
  • 0–19   — No aplica: otra disciplina o función; sin base relevante.

REGLAS DE PUNTUACIÓN:

1. skills_score: refleja la proporción de habilidades REQUERIDAS en estado CUBIERTA. Cada CUBIERTA sube; cada PARCIAL aporta poco; cada AUSENTE baja. Si solo cubre una minoría, cae a banda 40–59 o menos, aunque tenga mucha profundidad en esa minoría. Banda 90–100 solo si las cubre TODAS con solidez.

2. experience_score: relevancia de su trayectoria contra la FUNCIÓN central del puesto (no el título): años afines, seniority, logros y progresión. Si su función principal es de OTRA área, banda baja aunque acumule muchos años.

3. education_score: alineación de su formación con la DISCIPLINA central del puesto. Otra disciplina es banda baja aunque comparta una herramienta o curso suelto.

4. DISCRIMINA: si dos candidatos difieren en evidencia, sus puntajes deben diferir. No coloques las tres dimensiones en el mismo número por defecto; cada una se justifica por su propia evidencia.

5. relevant_experience_years: suma SOLO años en roles cuya FUNCIÓN coincide con la del puesto (el Título aparece más abajo en DATOS_DEL_PUESTO; misma área funcional, no título idéntico). Excluye prácticas, voluntariado y áreas no relacionadas. 0 si no hay experiencia afín.

6. missing_critical_skills: array con las REQUERIDAS en estado AUSENTE (juzga por significado: si tiene un equivalente, NO va aquí). Lista vacía [] si las cubre todas.

7. explanation: 2-3 frases (máx 60 palabras), claras y sin tecnicismos, con fortalezas y brechas.

8. guia_entrevista: EXACTAMENTE 3 preguntas, una de cada tipo. Cortas, abiertas y concretas.

ESTRUCTURA JSON OBLIGATORIA:
{
  "_razonamiento_previo": "resultado del emparejamiento (CUBIERTAS/PARCIALES/AUSENTES con evidencia), años afines nombrando roles, y pertinencia de la formación",
  "skills_score": 0,
  "experience_score": 0,
  "education_score": 0,
  "relevant_experience_years": 0,
  "missing_critical_skills": ["habilidad requerida AUSENTE"],
  "explanation": "2-3 frases claras, sin tecnicismos: fortalezas y brechas",
  "guia_entrevista": [
    {"tipo": "validar_logro", "pregunta": "..."},
    {"tipo": "explorar_brecha", "pregunta": "..."},
    {"tipo": "validar_inferencia", "pregunta": "..."}
  ]
}

<DATOS_DEL_PUESTO>
Título: $job_title
Experiencia mínima requerida: $min_experience_years años
Habilidades REQUERIDAS: $required_skills
Habilidades DESEABLES: $preferred_skills
Descripción: $job_description
</DATOS_DEL_PUESTO>

<DATOS_DEL_CANDIDATO>
Nota: este candidato se identifica internamente como "el candidato". No se incluyen su nombre, contactos ni datos identificatorios — evalúa el fit únicamente con la información profesional siguiente (principio de minimización LPDP Art. 6.4).

Habilidades detectadas: $candidate_skills

Trayectoria profesional:
$experience_block

Formación académica y certificaciones:
$education_block

Idiomas: $languages_block

Resumen profesional: $candidate_summary
</DATOS_DEL_CANDIDATO>

RECORDATORIO FINAL:
- Primero el emparejamiento semántico con evidencia, después los números.
- Juzga por significado (sinónimos, equivalentes, transferible), nunca por coincidencia literal.
- Usa todo el rango y discrimina: candidatos distintos, números distintos.
- Si un dato no aparece en el CV, no lo inventes (asume que no lo tiene).
- Devuelve SOLO el JSON con la forma exacta de arriba, sin texto antes ni después, sin Markdown.