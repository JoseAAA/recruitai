Extrae los datos estructurados de esta vacante laboral y devuelve UN SOLO JSON con la forma indicada. Si un dato no aparece en el texto, usa null o lista vacía — NUNCA inventes ni infieras.

PRINCIPIO RECTOR: extraes solo lo que el texto AFIRMA. No deduces de pistas indirectas. Si tienes que "razonar para adivinar" un valor, el valor correcto es null.

CAMPOS A EXTRAER:

- title (string, obligatorio): título exacto del puesto, tal como aparece.
- department (string|null): área / gerencia / departamento. Solo si aparece literal.
- seniority_level (string|null): uno de junior, mid-level, senior, lead, manager. SOLO si el texto lo declara explícitamente (en el título o en el cuerpo: "Senior", "Jefe", "Líder", "Gerente", "Junior", "Semi-senior"). Si solo se infiere por los años de experiencia o por el tono, déjalo null. No deduzcas seniority de los requisitos.
- work_modality (string|null): uno de remote, hybrid, onsite. Solo si el texto usa "remoto / presencial / híbrido / home office / remote / on-site / hybrid". Sin valor por defecto.
- location (string|null): ciudad / distrito / país / sede. Solo si el texto lo declara.
- industry (string|null): sector. Solo si está mencionado.
- education_level (string|null): mapea a uno de bachelor / master / phd / associate / high_school:
  · "Bachiller", "Titulado", "Licenciado", "Ingeniero/a", "Grado universitario", "Bachelor's", "BSc", "BA" → bachelor
  · "Maestría", "MBA", "Master's", "MSc", "Posgrado" → master
  · "Doctorado", "PhD" → phd
  · "Técnico Superior", "Associate" → associate
  · "Secundaria", "High school" → high_school
  · Si no se especifica → null. NUNCA mapees "Bachiller" a master.
  · Si pide varios niveles alternativos (ej. "Bachiller o Técnico"), usa el MÍNIMO exigido (associate).
- min_experience_years (int): entero. Reglas de rango:
  · "3-5 años" → 3 (el mínimo del rango)
  · "+5 años" / "más de 5 años" / "5+ años" → 5
  · "5-3 años" o rango invertido → usa el número menor (3)
  · sin datos → 0. Nunca uses strings.
- description (string|null): resumen objetivo de 2-4 oraciones del rol, en tus palabras pero solo con hechos del texto. No agregues atractivos ni adjetivos que el texto no use.
- responsibilities (array de strings): tareas/funciones listadas, cada una como ítem. Si no hay, [].
- key_objectives (array de strings): metas / KPIs / objetivos medibles. Si no hay, [].
- required_skills (array de strings): habilidades del puesto. Regla de asignación:
  · Si HAY secciones explícitas ("indispensables / requeridos / obligatorios / requisitos / must-have / required"), incluye SOLO las de esas secciones.
  · Si NO hay ninguna sección que separe requeridas de deseables, trata TODAS las skills mencionadas como required_skills (y preferred_skills queda []).
- preferred_skills (array de strings): habilidades bajo secciones "deseables / opcionales / valorables / nice-to-have / preferred / se valorará". Si no existe tal sección, [].
- required_languages (array de objetos): cada ítem {idioma, nivel, obligatorio}.
  · nivel ∈ {Básico, Intermedio, Avanzado, Nativo, Bilingüe}. Si el texto no da nivel, usa null en nivel.
  · obligatorio = true si es requisito, false si es deseable.
  · NO confundas "habilidades comunicativas" / "comunicación efectiva" con idiomas.
  · NO incluyas el idioma en que está escrito el documento, salvo que se pida explícitamente.
  · Si no hay, [].

REGLAS DE DECISIÓN (resuelven los casos ambiguos):
1. required vs preferred se decide por la SECCIÓN donde aparece la skill, NO por palabras dentro del nombre.
2. Una misma skill NUNCA aparece en ambos arrays. Si el texto la repite en ambas secciones, prevalece required.
3. Pares "Etiqueta: Valor" (Departamento: X, Modalidad: Y): copia el valor literal al campo correspondiente.
4. Español e inglés son ambos válidos como idioma del documento.
5. Si un mismo dato aparece con dos valores contradictorios, usa el primero que aparece en el texto y no inventes una conciliación.

RECORDATORIO ANTES DE RESPONDER (autocontrol):
- ¿Cada valor que pusiste está respaldado por texto literal? Si no, cámbialo a null/[].
- ¿required_skills y preferred_skills no comparten ningún ítem?
- ¿seniority y education salen de una declaración explícita, no de una inferencia?

ESTRUCTURA JSON OBLIGATORIA:
{
  "title": "",
  "department": null,
  "seniority_level": null,
  "work_modality": null,
  "location": null,
  "industry": null,
  "education_level": null,
  "min_experience_years": 0,
  "description": null,
  "responsibilities": [],
  "key_objectives": [],
  "required_skills": [],
  "preferred_skills": [],
  "required_languages": []
}

<TEXTO_PUESTO>
$job_text
</TEXTO_PUESTO>

RECORDATORIO FINAL:
- Lo que no esté en el texto, déjalo null o []. No completes con suposiciones plausibles.
- Devuelve SOLO el JSON, sin texto antes ni después, sin Markdown, sin comentarios.