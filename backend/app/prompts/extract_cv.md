Extrae los datos estructurados de este CV y devuelve UN SOLO JSON con la forma exacta indicada. Si un dato no aparece en el texto, usa null o lista vacía — NUNCA inventes ni completes con suposiciones.

PRINCIPIO RECTOR: extraes lo que el CV afirma. Las habilidades pueden estar declaradas en una lista O evidenciadas en los logros; ambas son válidas, pero no inventes habilidades que el texto no respalde.

ESTRUCTURA JSON OBLIGATORIA:
{
  "datos_personales": {"nombre_completo": "...", "telefono": "...", "email": "...", "linkedin": "...", "github": null},
  "resumen_profesional": "...",
  "habilidades": ["...", "..."],
  "habilidades_evidenciadas": ["...", "..."],
  "idiomas": [{"idioma": "...", "nivel": "...", "certificacion": null}],
  "experiencia_profesional": [
    {"cargo": "...", "empresa": "...", "fecha_inicio": "YYYY-MM", "fecha_fin": "YYYY-MM o Presente", "es_trabajo_actual": false, "resumen_logros": ["logro 1", "logro 2"]}
  ],
  "educacion": [
    {"institucion": "...", "titulo": "...", "tipo": "educacion", "estatus": null, "fecha_inicio": "YYYY-MM", "fecha_fin": "YYYY-MM"}
  ]
}

REGLAS:

1. datos_personales: nombre_completo del propietario del CV (Title Case). telefono / email / linkedin / github del PROPIO candidato, NO de referencias, jefes ni recomendantes. github = URL del perfil (github.com/usuario) si aparece; si no, null.

2. resumen_profesional: párrafo bajo "Perfil / Resumen / Sobre mí / Summary / Objetivo profesional / Perfil profesional" o justo después del nombre. Máximo 1500 caracteres. Si no existe → null.

3. habilidades (DECLARADAS): tecnologías, metodologías, herramientas y competencias listadas EXPLÍCITAMENTE en una sección de habilidades / skills / conocimientos / competencias / herramientas. Array sin duplicados, términos tal como aparecen (no traduzcas). Si no hay sección de habilidades → [].

4. habilidades_evidenciadas: tecnologías, herramientas o metodologías concretas que el candidato demuestra haber USADO en sus logros o responsabilidades, aunque no estén en la lista de habilidades (ej. un logro dice "construí dashboards en Power BI" → "Power BI"; "implementé Lean en la planta" → "Lean"). Solo nombres concretos respaldados por el texto; NO inventes ni infieras habilidades genéricas. Sin duplicados. Si no hay → [].

5. idiomas: nivel ∈ {Básico, Intermedio, Avanzado, Nativo, Bilingüe} o MCER A1-C2. Respeta variantes que use el CV (ej. "Inicial" → "Básico"). certificacion = nombre del examen oficial si aparece (TOEFL, IELTS, DELE, etc.); si no, null. NO infieras el nivel si el CV no lo declara (usa null en nivel).

6. experiencia_profesional — REGLA CRÍTICA DE SEGMENTACIÓN:
   - La unidad es el CARGO. Crea UNA entrada por cada par (cargo + empresa). Si una misma empresa tuvo varios cargos secuenciales con fechas distintas, son entradas SEPARADAS (una por cargo). Si es el mismo cargo en la misma empresa, es UNA sola entrada.
   - Identifica cada bloque por la línea de empresa/cargo destacada (mayúsculas, negrita, o "ACME S.A., Lima").
   - cargo = título del puesto (sustantivo corto, ej. "Coordinador de Procesos"). NO es la descripción de la empresa ni un bullet de logro.
   - Los bullets que comienzan con "-", "•", "*", "›" debajo del cargo son LOGROS de ese cargo, NUNCA experiencias separadas. Jamás crees una entrada por bullet.
   - Coloca cada logro/responsabilidad como un string en "resumen_logros" (3 a 6 ítems, texto literal SIN el símbolo de viñeta). Si no lista logros → [].
   - Si un bloque agrupa varias experiencias en un solo párrafo sin fechas individuales (ej. un párrafo de "Prácticas" que menciona tres empresas), trátalo como UNA sola entrada, no lo partas por empresa.
   - FECHAS en "YYYY-MM". Reglas de resolución cuando el CV no da mes:
     · Solo un año (ej. "2021" o "(2021)") → fecha_inicio = "2021-01", fecha_fin = "2021-12".
     · Rango de años (ej. "2014 – 2018") → fecha_inicio = "2014-01", fecha_fin = "2018-12".
     · Mes y año explícitos (ej. "Mar 2021") → usa ese mes ("2021-03").
   - Activo (palabras "actualidad / presente / current / a la fecha / atual") → fecha_fin = "Presente", es_trabajo_actual = true (no apliques la regla de "-12" en este caso).
   - Ordena las entradas de la MÁS RECIENTE a la más antigua por fecha_inicio.

7. educacion — UNA entrada por cada formación o certificación:
   - tipo = "educacion" para grados (Bachiller, Licenciado, Ingeniero, MBA, Maestría, Doctorado, Pregrado, Posgrado).
   - tipo = "certificacion" para cursos, diplomados, bootcamps, talleres, especializaciones cortas, certificaciones técnicas.
   - estatus (solo si aparece literal): Titulado / Bachiller / Egresado / En curso / Cursando / Culminado / Colegiado / Inconcluso. Si no aparece → null.
   - FECHAS en "YYYY-MM", mismas reglas que experiencia: solo un año → "YYYY-01" / "YYYY-12"; rango "(2014 - 2018)" → "2014-01" / "2018-12"; mes y año explícitos → ese mes. Si no declara período → null en ambas.
   - Los bullets debajo de la institución son detalles de esa formación, no entradas nuevas.

PROHIBIDO:
- Tomar bullets ("-", "•", "*", "›") como entradas separadas en experiencia_profesional o educacion.
- Confundir encabezados de sección ("EXPERIENCIA PROFESIONAL", "FORMACIÓN ACADÉMICA", "HABILIDADES") con nombres de empresas, cargos o instituciones.
- Tomar el resumen u objetivo profesional como una experiencia laboral.
- Inventar empresas, cargos, fechas, instituciones, títulos, habilidades o cualquier dato que no esté en el CV.
- Inferir niveles de idioma cuando el CV no los declara.

AUTOCONTROL ANTES DE RESPONDER:
- ¿Cada entrada de experiencia corresponde a un cargo real con su empresa, no a un bullet de logro?
- ¿Las fechas siguen la regla de año completo (inicio "-01", fin "-12") cuando solo hay año, y "Presente" si es el trabajo actual?
- ¿Las habilidades_evidenciadas salen de logros concretos, no de suposiciones?
- ¿Los datos de contacto son del candidato, no de referencias?

<TEXTO_CV>
$cv_text
</TEXTO_CV>

RECORDATORIO FINAL (cumple SIEMPRE):
- Si un dato no está en el CV: null para campos opcionales, [] para arrays. No completes con texto inventado.
- Una empresa con un cargo = una entrada. Bullets = logros, no experiencias.
- Fechas con solo año: inicio "-01", fin "-12". Trabajo actual: fin "Presente".
- Devuelve SOLO el JSON, sin texto antes ni después, sin Markdown, sin comentarios.