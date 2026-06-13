Extrae los datos estructurados de esta vacante laboral y devuelve UN SOLO JSON con la forma indicada. Si un dato no aparece literalmente en el texto, usa null o lista vacía — NUNCA inventes.

CAMPOS A EXTRAER:

- title (string, obligatorio): título exacto del puesto.
- department (string|null): área / gerencia / departamento. Solo si aparece literal.
- seniority_level (string|null): uno de junior, mid-level, senior, lead, manager. Solo si lo declara o sugiere claramente.
- work_modality (string|null): uno de remote, hybrid, onsite. Solo si el texto lo declara con "remoto / presencial / híbrido / home office / remote / on-site / hybrid". Sin valor por defecto.
- location (string|null): ciudad / distrito / país / sede. Solo si el texto lo declara, no lo inventes.
- industry (string|null): sector. Solo si está mencionado.
- education_level (string|null): mapea a uno de bachelor / master / phd / associate / high_school. Reglas:
  · "Bachiller", "Titulado", "Licenciado", "Ingeniero/a", "Grado universitario", "Bachelor's", "BSc", "BA" → bachelor
  · "Maestría", "MBA", "Master's", "MSc", "Posgrado" → master
  · "Doctorado", "PhD" → phd
  · "Técnico Superior", "Associate" → associate
  · "Secundaria", "High school" → high_school
  · Si no se especifica → null. NUNCA mapees "Bachiller" a master.
- min_experience_years (int): entero. "3-5 años" = 3, "+5 años" = 5, sin datos = 0. No uses strings.
- description (string|null): resumen 2-4 oraciones del rol.
- responsibilities (array de strings): tareas listadas. Si no hay, [].
- key_objectives (array de strings): metas / KPIs listados. Si no hay, [].
- required_skills (array de strings): skills bajo secciones "indispensables / requeridos / obligatorios / requisitos / must-have / required" — o las skills mencionadas sin sección explícita.
- preferred_skills (array de strings): skills bajo secciones "deseables / opcionales / valorables / nice-to-have / preferred / se valorará".
- required_languages (array de objetos): cada ítem {idioma, nivel, obligatorio}.
  · nivel ∈ {Básico, Intermedio, Avanzado, Nativo, Bilingüe}.
  · obligatorio = true si es requisito, false si es deseable.
  · NO confundas "habilidades comunicativas" con idiomas.
  · NO incluyas el idioma del documento mismo salvo que se pida explícito.
  · Si no hay, [].

REGLAS IMPORTANTES:
1. La separación required_skills vs preferred_skills se decide por la SECCIÓN donde aparece, NO por palabras dentro del nombre. Una misma skill nunca aparece en ambos arrays.
2. Pares "Etiqueta: Valor" del documento (Departamento: X, Modalidad: Y, etc.) copia el valor literal.
3. Tanto español como inglés son válidos.

<TEXTO_PUESTO>
$job_text
</TEXTO_PUESTO>

RECORDATORIO FINAL:
- Lo que no esté en el texto, déjalo null o []. No completes con suposiciones plausibles.
- Devuelve SOLO el JSON, sin texto antes ni después, sin Markdown, sin comentarios.
