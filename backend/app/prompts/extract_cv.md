Extrae los datos estructurados de este CV y devuelve UN SOLO JSON con la forma exacta indicada. Si un dato no aparece literalmente en el texto, usa null o lista vacía — NUNCA inventes ni completes con suposiciones.

ESTRUCTURA JSON OBLIGATORIA:
{
  "datos_personales": {"nombre_completo": "...", "telefono": "...", "email": "...", "linkedin": "...", "github": null},
  "resumen_profesional": "...",
  "habilidades": ["...", "..."],
  "idiomas": [{"idioma": "...", "nivel": "...", "certificacion": null}],
  "experiencia_profesional": [
    {"cargo": "...", "empresa": "...", "fecha_inicio": "YYYY-MM", "fecha_fin": "YYYY-MM o Presente", "es_trabajo_actual": false, "resumen_logros": ["logro o responsabilidad 1", "logro o responsabilidad 2"]}
  ],
  "educacion": [
    {"institucion": "...", "titulo": "...", "tipo": "educacion", "estatus": null, "fecha_inicio": "YYYY-MM", "fecha_fin": "YYYY-MM"}
  ]
}

REGLAS:

1. datos_personales: nombre_completo del propietario del CV (Title Case). telefono / email / linkedin / github del PROPIO candidato, NO de referencias, jefes ni recomendantes. github = URL del perfil (github.com/usuario) si aparece; si no, null.

2. resumen_profesional: párrafo bajo "Perfil / Resumen / Sobre mí / Summary / Objetivo profesional" o justo después del nombre. Máximo 1500 caracteres. Si no existe → null.

3. habilidades: tecnologías, metodologías, herramientas y competencias listadas. Array sin duplicados, términos tal como aparecen en el CV (no traduzcas).

4. idiomas: nivel ∈ {Básico, Intermedio, Avanzado, Nativo, Bilingüe} o MCER A1-C2. certificacion = nombre del examen oficial si aparece (TOEFL, IELTS, DELE, etc.) — si no se menciona, null.

5. experiencia_profesional — REGLA CRÍTICA:
   - UNA entrada POR CADA EMPRESA distinta. Si una empresa tuvo varios cargos secuenciales, son entradas separadas.
   - Identifica cada bloque por la línea de empresa destacada (mayúsculas, encabezado en negrita, o "ACME S.A., Lima").
   - cargo = título del puesto (sustantivo corto tipo "Coordinador de Procesos"). NO es la descripción de la empresa ni un bullet de logro.
   - Los bullets que comienzan con "-", "•", "*", "›" debajo del cargo son LOGROS de ese cargo, NO experiencias separadas. Nunca crees una entrada por bullet.
   - Coloca cada logro/responsabilidad del cargo como un string dentro de "resumen_logros" (entre 3 y 6 ítems máximo, texto literal del logro SIN el símbolo de viñeta). Si el cargo no lista logros → "resumen_logros": [].
   - Fechas en formato "YYYY-MM" (usa "YYYY-01" si solo aparece el año). Si está activo (palabras "actualidad / presente / current / a la fecha") → fecha_fin = "Presente", es_trabajo_actual = true.

6. educacion — UNA entrada por cada formación o certificación:
   - tipo = "educacion" para grados universitarios (Bachiller, Licenciado, Ingeniero, MBA, Maestría, Doctorado, Pregrado, Posgrado).
   - tipo = "certificacion" para cursos, diplomados, bootcamps, talleres, especializaciones cortas, certificaciones técnicas.
   - estatus (solo si aparece literal en el texto): Titulado / Bachiller / Egresado / En curso / Cursando / Culminado / Colegiado / Inconcluso. Si no aparece → null.
   - fecha_inicio / fecha_fin de cada formación en formato "YYYY-MM" (usa "YYYY-01" si solo aparece el año; ej. "(2014 - 2018)" → fecha_inicio "2014-01", fecha_fin "2018-01"). Si la formación no declara período → null.
   - Los bullets debajo de la institución son detalles de esa formación, no entradas nuevas.

PROHIBIDO:
- Tomar bullets ("-", "•", "*", "›") como entradas separadas en experiencia_profesional o educacion.
- Confundir encabezados de sección ("EXPERIENCIA PROFESIONAL", "FORMACIÓN ACADÉMICA", "HABILIDADES") con nombres de empresas, cargos o instituciones.
- Tomar el resumen profesional o un objetivo profesional como una experiencia laboral.
- Inventar empresas, cargos, fechas, instituciones, títulos o cualquier dato que no esté literalmente en el CV.
- Inferir niveles de idioma cuando el CV no los declara.

<TEXTO_CV>
$cv_text
</TEXTO_CV>

RECORDATORIO FINAL (cumple SIEMPRE):
- Si un dato no está en el CV: null para campos opcionales, lista vacía [] para arrays. No completes con texto inventado.
- Una empresa = una entrada. Bullets = logros, no experiencias.
- Devuelve SOLO el JSON, sin texto antes ni después, sin Markdown, sin comentarios.
