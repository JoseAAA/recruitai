---
version: alpha
name: Slate Pro
description: >
  Sistema de diseño portable para dashboards B2B, SaaS internos y herramientas
  de productividad. Modo oscuro por defecto, paleta neutra slate con un único
  primario azul, tipografía Inter y íconos Material Symbols Outlined. Pensado
  para reutilizarse en múltiples proyectos cambiando solo el color primario.
colors:
  primary: "#2563eb"
  primary-hover: "#1d4ed8"
  primary-soft: "#dbeafe"
  on-primary: "#ffffff"

  background: "#0f172a"
  surface: "#1e293b"
  surface-raised: "#334155"
  overlay: "#020617"

  text-primary: "#f8fafc"
  text-secondary: "#cbd5e1"
  text-muted: "#94a3b8"
  text-disabled: "#64748b"

  border: "#334155"
  border-strong: "#475569"
  divider: "#1e293b"

  success: "#10b981"
  success-soft: "#064e3b"
  warning: "#f59e0b"
  warning-soft: "#78350f"
  danger: "#f43f5e"
  danger-soft: "#7f1d1d"
  info: "#3b82f6"
  info-soft: "#1e3a8a"

  score-excellent: "#34d399"
  score-good: "#4ade80"
  score-fair: "#fbbf24"
  score-poor: "#fb7185"

typography:
  display:
    fontFamily: Inter
    fontSize: 1.875rem
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.02em
  h1:
    fontFamily: Inter
    fontSize: 1.5rem
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: -0.01em
  h2:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: 700
    lineHeight: 1.3
  h3:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 600
    lineHeight: 1.4
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: 500
    lineHeight: 1.4
  overline:
    fontFamily: Inter
    fontSize: 0.625rem
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 0.1em
  numeric:
    fontFamily: Inter
    fontSize: 1.5rem
    fontWeight: 700
    lineHeight: 1.2
    fontFeature: "'tnum' on"

rounded:
  none: 0px
  sm: 4px
  md: 6px
  lg: 8px
  xl: 12px
  2xl: 16px
  full: 9999px

spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 48px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.xl}"
    padding: "{spacing.sm} {spacing.lg}"
    height: 40px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm} {spacing.lg}"
    height: 40px
  button-secondary-hover:
    backgroundColor: "{colors.surface-raised}"
  button-destructive:
    backgroundColor: "transparent"
    textColor: "{colors.danger}"
    typography: "{typography.label}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm} {spacing.lg}"
  button-destructive-hover:
    backgroundColor: "{colors.danger-soft}"

  input:
    backgroundColor: "{colors.background}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md} {spacing.lg}"
    height: 44px
  input-focus:
    backgroundColor: "{colors.background}"
    textColor: "{colors.text-primary}"

  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.2xl}"
    padding: "{spacing.xl}"
  card-interactive-hover:
    backgroundColor: "{colors.surface-raised}"

  sidebar:
    backgroundColor: "{colors.background}"
    textColor: "{colors.text-muted}"
    width: 256px
  sidebar-item:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm} {spacing.md}"
  sidebar-item-hover:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
  sidebar-item-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"

  header:
    backgroundColor: "{colors.background}"
    height: 64px
    padding: "0 {spacing.xl}"

  badge-success:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    padding: "{spacing.xs} {spacing.md}"
  badge-warning:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    padding: "{spacing.xs} {spacing.md}"
  badge-danger:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    padding: "{spacing.xs} {spacing.md}"
  badge-info:
    backgroundColor: "{colors.info-soft}"
    textColor: "{colors.info}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    padding: "{spacing.xs} {spacing.md}"

  avatar:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    size: 36px

  kpi-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.2xl}"
    padding: "{spacing.xl}"
    height: 120px
---

## Overview

**Productive Calm meets Operational Clarity.** Slate Pro proyecta una interfaz
de trabajo seria, densa pero respirable, pensada para sesiones largas frente
a la pantalla: reclutadores revisando candidatos, analistas filtrando datos,
administradores configurando un sistema.

La estética parte de tres decisiones:

- **Oscuro por defecto.** Reduce fatiga visual en jornadas extensas y proyecta
  un tono profesional/técnico. El modo claro existe como alternativa, no como
  estado primario.
- **Slate como neutral.** Más frío que `gray` y más cálido que `zinc` — el
  punto medio de la familia de neutros de Tailwind. Comunica seriedad sin
  caer en lo institucional gris.
- **Azul único como acción.** Un solo color saturado (`#2563eb`) concentra
  toda la "atención clickeable". Esto disciplina la jerarquía: si algo es
  azul, es accionable; si no lo es, es información.

El sistema es **portable**. Para llevarlo a otro proyecto basta con
intercambiar `colors.primary` y `colors.primary-hover` por un par equivalente
(saturación ≥ 70%, luminosidad ~45–55%). El resto del sistema permanece
estable.

## Colors

La paleta se organiza en cuatro grupos: **marca**, **superficies**, **texto**
y **semántica**.

- **Primary (`#2563eb`):** Único color de marca. Aparece en botones primarios,
  links activos, item de navegación seleccionado y ring de foco. Su variante
  `primary-soft` (`#dbeafe`) se usa solo en chips o highlights muy puntuales.
- **Background (`#0f172a`):** Lienzo de la aplicación y sidebar. Es slate-900.
- **Surface (`#1e293b`):** Cards, panels, inputs en estado normal. Slate-800,
  un escalón visible sobre el background.
- **Surface-raised (`#334155`):** Hover sobre cards y zonas elevadas. Slate-700.
- **Text-primary (`#f8fafc`):** Texto principal. Casi blanco, pero matizado
  para no quemar contra slate-900.
- **Text-secondary / muted (`#cbd5e1` / `#94a3b8`):** Metadatos, descripciones,
  timestamps. Mantienen contraste AA pero retroceden visualmente.
- **Semánticas (success, warning, danger, info):** Cada una con su pareja
  `*-soft` para fondos de badges. Nunca se usan como color decorativo;
  significan **estado**, no estética.
- **Score (excellent/good/fair/poor):** Escala específica para puntajes 0–100
  (≥85 / 70–84 / 50–69 / <50). Reutilizable en cualquier dominio con scoring.

**Contraste:** todos los pares texto/fondo cumplen WCAG AA. Texto sobre
`primary` y texto sobre `*-soft` se han verificado contra el fondo del badge,
no contra el fondo de la página.

## Typography

**Inter** es la única familia tipográfica del sistema. Se carga vía
`next/font/google` (self-hosted, sin CLS). Está optimizada para UI:
metricas idénticas en pesos 400–700, números tabulares opcionales,
excelente legibilidad a tamaños pequeños.

La escala es **deliberadamente corta** — nueve estilos cubren todos los casos:

- `display` (30px) — solo para hero/landing internos. Rara vez en este sistema.
- `h1` (24px) — título de página, uno por vista.
- `h2` (18px) — título de sección.
- `h3` (16px) — título de card.
- `body-md` (14px) — texto general, **default del sistema**.
- `body-sm` (12px) — descripciones secundarias, ayudas inline.
- `label` (14px / peso 500) — etiquetas de formulario, botones, nav items.
- `overline` (10px / peso 700 / uppercase) — categorías, labels de sección
  en sidebars y headers.
- `numeric` (24px / `tnum`) — KPIs y métricas grandes. Activa números
  tabulares para evitar "saltos" al actualizar el valor.

**Reglas:**
- Nunca usar pesos < 400. `font-thin` es ilegible en modo oscuro.
- Títulos siempre con `tracking-tight`; overlines con `tracking-widest`.
- No combinar Inter con otra sans en el mismo proyecto.

## Layout

La aplicación tiene un **shell de tres regiones**:

```
┌──────────────────────────────────────────────┐
│ Sidebar 256px │  Header 64px                 │
│               ├──────────────────────────────┤
│  background   │  Content                     │
│               │  max-w 1280px, mx-auto       │
│               │  padding 16px (32px en md+)  │
│               │  flex-col gap 32px           │
└──────────────────────────────────────────────┘
```

- **Sidebar:** ancho fijo 256px. Oculto en `< 768px` y reemplazado por menú.
- **Header:** alto fijo 64px, sticky, con `backdrop-blur` sutil. Contiene
  indicador de estado del sistema, toggle de tema y acción primaria.
- **Content:** scroll independiente del shell, ancho máximo 1280px
  (`max-w-7xl`) para evitar líneas demasiado largas en monitores grandes.

**Escala de espaciado (base 4px):**

- `xs` 4px — gap entre icono y texto en chips muy compactos
- `sm` 8px — gap entre items inline, padding vertical de inputs compactos
- `md` 12px — gap dentro de sidebar items, padding lateral de botones
- `lg` 16px — gap entre items de form, padding de inputs
- `xl` 24px — gap entre secciones, padding interno de cards
- `2xl` 32px — gap entre bloques principales de la página
- `3xl` 48px — separación de empty states, padding de modales grandes

**Grids estándar:**
- KPI strip: `grid-cols-2 lg:grid-cols-4 gap-4`
- Layout principal: `grid-cols-1 lg:grid-cols-5 gap-6` (3+2 columnas)
- Listados de cards: `grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6`

## Elevation & Depth

La elevación se comunica sobre todo por **luminosidad de fondo**, no por
sombras. En modo oscuro las sombras se ven débiles; en su lugar, cada nivel
de elevación es un escalón más claro de slate:

- Nivel 0 — Background (`#0f172a`) — Lienzo, sidebar, header.
- Nivel 1 — Surface (`#1e293b`) — Cards, inputs, panels.
- Nivel 2 — Surface-raised (`#334155`) — Hover de cards, dropdowns, popovers.
- Nivel 3 — Overlay (`#020617`) — Modales y backdrops; más oscuro que el fondo
  para invertir la jerarquía y enfocar atención.

**Sombras** se usan con moderación y siempre tintadas:

- Botón primario y nav item activo: sombra azul `shadow-lg shadow-primary/20`.
  Es el único caso donde la sombra es estructural, no decorativa.
- Cards estándar: `shadow-sm` muy sutil, sirve más en modo claro que en oscuro.
- Cards interactivas al hover: `shadow-md`.

**Bordes** son tan importantes como las sombras: separan sidebar/header del
contenido (`border-slate-700/800`) y delinean cards en modo oscuro donde la
sombra no se ve.

## Shapes

Border-radius escalonado, regido por una **regla de jerarquía**:

> Dentro de un componente, los hijos siempre tienen radius **≤** al del padre.
> Un input `rounded-lg` dentro de una card `rounded-2xl` es correcto. Lo
> inverso rompe la jerarquía visual.

- `sm` (4px) — tags muy pequeños, etiquetas inline.
- `md` (6px) — derivado interno, raro de usar directamente.
- `lg` (8px) — **default**: inputs, botones secundarios, nav items, popovers.
- `xl` (12px) — botones primarios, modales pequeños, tooltips.
- `2xl` (16px) — **cards principales**, paneles de la página.
- `full` — avatares, indicadores de estado, chips circulares, badges con dot.

**Iconografía:** Material Symbols Outlined es el único sistema de iconos.
Variante `outlined` por defecto; `fill` solo para indicar **estado activo**
(item de nav seleccionado, favorito marcado, notificación con contenido).
Tamaños: 16px inline, 18–20px en botones/nav, 24px en KPI cards, 48px en
empty states, 120px en errores de página completa (404, sin conexión).

## Components

### Button — primary

Acción principal de la página. Solo **uno por contexto** (header, formulario,
modal). Usa color primario sobre blanco, radius `xl`, sombra tintada.

```tsx
<button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold
                   text-white bg-primary rounded-xl
                   hover:bg-primary/90 transition-colors
                   shadow-sm shadow-primary/30
                   disabled:opacity-50 disabled:cursor-not-allowed">
  <span className="material-symbols-outlined text-[18px]">add</span>
  Nueva Vacante
</button>
```

### Button — secondary

Acciones complementarias (Cancelar, Filtrar, Exportar). Surface neutro,
radius `lg`, sin sombra.

```tsx
<button className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                   text-slate-300 bg-slate-800 border border-slate-700
                   rounded-lg hover:bg-slate-700 transition-colors">
  Cancelar
</button>
```

### Button — destructive

Acciones irreversibles (Eliminar). Texto en `danger`, fondo transparente que
se ilumina con `danger-soft` al hover. **Siempre acompañado de confirmación
modal.**

```tsx
<button className="px-4 py-2 text-sm font-medium text-rose-400
                   hover:bg-rose-500/10 rounded-lg transition-colors">
  Eliminar
</button>
```

### Input

Inputs con icono a la izquierda (opcional), foco con ring azul tenue.

```tsx
<div className="relative">
  <span className="absolute left-3 top-1/2 -translate-y-1/2
                   material-symbols-outlined text-slate-400 text-[20px]">mail</span>
  <input
    className="w-full pl-10 pr-4 py-3
               bg-slate-900 border border-slate-700 rounded-lg
               text-white placeholder-slate-400
               focus:border-primary focus:outline-none
               focus:ring-2 focus:ring-primary/30 transition-all" />
</div>
```

### Card

Contenedor principal de información agrupada. Radius `2xl`, padding `xl`,
fondo `surface`, borde `slate-700`.

```tsx
<div className="bg-slate-800/60 border border-slate-700
                rounded-2xl p-6 shadow-sm">
  <h3 className="text-base font-bold text-white">Título</h3>
  <p className="text-xs text-slate-400 mt-1">Subtítulo</p>
</div>
```

### KPI Card

Variante de card para métricas numéricas. Incluye icono coloreado, label
uppercase, valor en tipografía `numeric`. Ancho flexible en grid 2/4 columnas.

```tsx
<div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-5">
  <div className="flex items-center gap-3 mb-3">
    <div className="p-2 rounded-lg bg-primary/10">
      <span className="material-symbols-outlined text-primary text-[24px]">work</span>
    </div>
    <span className="text-[10px] font-bold uppercase tracking-widest
                     text-slate-400">Vacantes Activas</span>
  </div>
  <p className="text-2xl font-bold text-white tabular-nums">12</p>
</div>
```

### Sidebar item

```tsx
// Inactivo
<a className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
              text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-all">
  <span className="material-symbols-outlined text-[20px]">dashboard</span>
  Panel de Control
</a>

// Activo
<a className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
              bg-primary text-white shadow-lg shadow-primary/20">
  <span className="material-symbols-outlined fill text-[20px]">dashboard</span>
  Panel de Control
</a>
```

### Badge (semántico)

Pill compacto con dot opcional para indicar estado.

```tsx
<span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full
                 text-xs font-medium
                 bg-emerald-500/10 text-emerald-400">
  <span className="size-1.5 rounded-full bg-emerald-500" />
  Contratado
</span>
```

Variantes: `success`, `warning`, `danger`, `info`, `neutral`.

### Avatar

```tsx
<div className="size-9 rounded-full bg-gradient-to-br from-primary to-indigo-500
                flex items-center justify-center text-white text-sm font-bold
                ring-2 ring-primary/30">
  JA
</div>
```

### Estados de pantalla

Toda página debe manejar tres estados además del feliz:

- **Loading:** icono `sync` 48px en `text-primary` con `animate-spin` +
  mensaje "Cargando…".
- **Error:** icono `cloud_off` o `error` 48px en `text-danger` + mensaje
  + botón "Reintentar".
- **Empty:** icono temático 48px en `text-slate-400` + título + descripción
  + CTA opcional para crear el primer recurso.

## Do's and Don'ts

### Color

✅ **Do** usar el color primario **solo** para acciones clickeables y estados
activos. Si todo es azul, nada lo es.

✅ **Do** tratar `success/warning/danger/info` como **estados**, no como
estética. Un check verde decorativo confunde al usuario.

❌ **Don't** introducir un segundo color de marca "para variar". Si necesitas
diferenciación, usa peso tipográfico o jerarquía espacial.

❌ **Don't** mezclar dos azules distintos. Si rebrandeas a otro proyecto,
cambia los dos tokens (`primary` y `primary-hover`) a la vez.

❌ **Don't** usar emerald/amber/rose en contextos sin significado semántico
("se ve bonito"). Rompe el contrato de color del sistema.

### Tipografía

✅ **Do** mantener la escala corta. Si un texto no encaja en uno de los nueve
estilos, primero revisa si el contenido está mal jerarquizado.

✅ **Do** usar `tabular-nums` en cualquier tabla o KPI donde el número se
actualice en vivo.

❌ **Don't** introducir una segunda familia tipográfica (mono está permitida
solo para IDs o código).

❌ **Don't** usar `font-thin` (100) o `font-light` (300). Se rompen en modo
oscuro.

### Layout y espaciado

✅ **Do** envolver el contenido en `max-w-7xl mx-auto`. Las líneas largas son
ilegibles.

✅ **Do** dejar respirar las cards. `p-5` o `p-6` es el default; menos satura.

❌ **Don't** mezclar `gap-3` y `gap-5` en grids hermanos. Elige uno de la
escala estándar (`gap-2/4/6/8`).

❌ **Don't** crear un grid de KPIs de 3 columnas. La estética se rompe; usa
2 o 4.

### Componentes

✅ **Do** reusar los componentes de la sección 7 antes de inventar variantes.
Si necesitas algo nuevo, primero verifica que no exista un patrón cercano.

✅ **Do** acompañar todo botón destructivo de una confirmación modal.

✅ **Do** dar foco visible (`focus:ring-2 focus:ring-primary/30`) a todos los
elementos interactivos. La navegación por teclado es accesibilidad mínima.

❌ **Don't** mezclar librerías de iconos. Material Symbols es exclusivo.
Si el proyecto destino no quiere cargar la fuente (~200KB), reemplaza el
sistema **completo** por Lucide, no mezcles.

❌ **Don't** comunicar estados solo por color. Acompaña siempre con icono o
texto — un usuario con daltonismo no distingue rojo de verde.

❌ **Don't** abusar de animaciones. Solo `transition-colors`, `animate-spin`,
`animate-pulse`, `animate-ping`. Nada de parallax, slides de página, ni
"micro-interacciones" decorativas. Esto es producto, no presentación.

### Rebranding

✅ **Do** cambiar solo `colors.primary` y `colors.primary-hover` al portar
Slate Pro a otro proyecto. El resto del sistema permanece estable.

❌ **Don't** bajar la saturación del primario para "verse más serio". Un
primario apagado hace que la UI parezca rota o deshabilitada.

❌ **Don't** mover los neutros a `gray` o `zinc`. Slate es parte del carácter
del sistema; cambiarlo es crear otro design system, no rebrandear este.
