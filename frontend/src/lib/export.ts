/**
 * Export utilities for RecruitAI.
 * Uses ExcelJS for full cell formatting support (colors, fonts, borders).
 */

import type { JobProfile, Candidate, MatchResult } from "@/lib/api";

// ── Status labels ─────────────────────────────────────────────────────────────
export const STATUS_LABELS: Record<string, string> = {
    new: "Nuevo", screening: "En Revisión", shortlisted: "Preseleccionado",
    interview: "Entrevista", offer: "Oferta", hired: "Contratado", rejected: "Descartado",
};

export interface ExportCandidate {
    full_name: string; email?: string; phone?: string; linkedin?: string;
    total_experience_years: number; skills: string[]; status: string;
    job_title?: string; match_score?: number; recommendation?: string;
    missing_skills?: string[]; bonus_skills?: string[];
}

export interface ExportOptions { baseFilename?: string; includeScoreColumns?: boolean; }

// ── Color palette (ARGB for ExcelJS) ──────────────────────────────────────────
const C = {
    // Backgrounds
    headerDark:  "FF1E293B",   // slate-900  — main header rows
    headerMid:   "FF334155",   // slate-700  — secondary headers
    titleBlue:   "FF1E40AF",   // blue-800   — title / section labels
    recGreenBg:  "FFD1FAE5",   // emerald-100
    recBlueBg:   "FFDBEAFE",   // blue-100
    recAmberBg:  "FFFEF3C7",   // amber-100
    recGrayBg:   "FFF1F5F9",   // slate-100
    altRow:      "FFF8FAFC",   // slate-50   — zebra stripe
    white:       "FFFFFFFF",
    kpiBlue:     "FFEFF6FF",   // blue-50
    kpiBlueBdr:  "FFBfdbfe",   // blue-200
    kpiGreen:    "FFF0FDF4",
    kpiGreenBdr: "FFbbf7d0",
    // Fonts
    fWhite:    "FFFFFFFF",
    fDark:     "FF0F172A",   // slate-950
    fBlue:     "FF1E40AF",   // blue-800
    fGreen:    "FF065F46",   // emerald-800
    fAmber:    "FF92400E",   // amber-800
    fGray:     "FF475569",   // slate-600
    fSlate:    "FF94A3B8",   // slate-400
    // Score thresholds
    scoreHigh:   "FFD1FAE5",  fScoreHigh:  "FF065F46",
    scoreMid:    "FFDBEAFE",  fScoreMid:   "FF1D4ED8",
    scoreLow:    "FFFEF3C7",  fScoreLow:   "FF92400E",
    scoreNone:   "FFF1F5F9",  fScoreNone:  "FF94A3B8",
};

function scoreStyle(v: number) {
    if (v >= 75) return { bg: C.scoreHigh, font: C.fScoreHigh };
    if (v >= 55) return { bg: C.scoreMid,  font: C.fScoreMid  };
    if (v >= 35) return { bg: C.scoreLow,  font: C.fScoreLow  };
    return             { bg: C.scoreNone,  font: C.fScoreNone  };
}

function recStyle(rec: string) {
    if (rec === "Altamente recomendado") return { bg: C.recGreenBg, font: C.fGreen };
    if (rec === "Buena opción")          return { bg: C.recBlueBg,  font: C.fBlue  };
    if (rec === "Considerar")            return { bg: C.recAmberBg, font: C.fAmber };
    return                                      { bg: C.recGrayBg,  font: C.fGray  };
}

function dateTag() {
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`;
}

// ── ExcelJS helpers ────────────────────────────────────────────────────────────
type XlCell = import("exceljs").Cell;
type XlRow  = import("exceljs").Row;
type XlWS   = import("exceljs").Worksheet;

function thin(color = "FFD1D5DB") {
    return { top: { style: "thin" as const, color: { argb: color } },
             bottom: { style: "thin" as const, color: { argb: color } },
             left:   { style: "thin" as const, color: { argb: color } },
             right:  { style: "thin" as const, color: { argb: color } } };
}

function applyHeaderRow(row: XlRow, bgArgb: string, cols: number) {
    row.height = 22;
    for (let c = 1; c <= cols; c++) {
        const cell = row.getCell(c);
        cell.font      = { bold: true, color: { argb: C.fWhite }, size: 10, name: "Calibri" };
        cell.fill      = { type: "pattern", pattern: "solid", fgColor: { argb: bgArgb } };
        cell.alignment = { horizontal: "center", vertical: "middle" };
        cell.border    = thin("FFFFFFFF");
    }
}

function applyDataRow(row: XlRow, bg: string, font: string, numCols: number, wrap = false) {
    row.height = wrap ? 30 : 18;
    for (let c = 1; c <= numCols; c++) {
        const cell = row.getCell(c);
        cell.font      = { color: { argb: font }, size: 10, name: "Calibri" };
        cell.fill      = { type: "pattern", pattern: "solid", fgColor: { argb: bg } };
        cell.alignment = { vertical: "middle", wrapText: wrap };
        cell.border    = thin();
    }
}

function sectionLabel(ws: XlWS, rowNum: number, text: string, cols: number) {
    const row = ws.getRow(rowNum);
    row.height = 20;
    const cell = row.getCell(1);
    cell.value = text.toUpperCase();
    cell.font  = { bold: true, color: { argb: C.fWhite }, size: 10, name: "Calibri" };
    cell.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: C.titleBlue } };
    cell.alignment = { horizontal: "left", vertical: "middle", indent: 1 };
    cell.border = thin(C.titleBlue);
    for (let c = 2; c <= cols; c++) {
        const cc = row.getCell(c);
        cc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: C.titleBlue } };
        cc.border = thin(C.titleBlue);
    }
    ws.mergeCells(rowNum, 1, rowNum, cols);
}

// ── CSV export (kept for legacy use) ─────────────────────────────────────────
function q(value: string | number | undefined | null): string {
    if (value == null || value === "") return "";
    const s = String(value);
    if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes(";"))
        return '"' + s.replace(/"/g, '""') + '"';
    return s;
}

export function exportCandidatesCsv(candidates: ExportCandidate[], options: ExportOptions = {}): void {
    const { baseFilename = "RecruitAI_Candidatos", includeScoreColumns = false } = options;
    const hasScores = includeScoreColumns || candidates.some(c => c.match_score != null);
    const headers = [
        "Nombre", "Email", "Teléfono", "LinkedIn", "Experiencia (años)", "Etapa del Pipeline", "Puesto Asignado",
        ...(hasScores ? ["Score IA (%)", "Recomendación IA", "Habilidades Faltantes", "Habilidades Bonus"] : []),
        "Habilidades",
    ];
    const rows = candidates.map(c => {
        const base = [q(c.full_name), q(c.email), q(c.phone), q(c.linkedin),
            q(c.total_experience_years > 0 ? c.total_experience_years : ""),
            q(STATUS_LABELS[c.status] ?? c.status), q(c.job_title ?? "")];
        const scoreFields = hasScores ? [
            q(c.match_score != null ? Math.round(c.match_score) : ""),
            q(c.recommendation ?? ""), q((c.missing_skills ?? []).join(" | ")), q((c.bonus_skills ?? []).join(" | ")),
        ] : [];
        return [...base, ...scoreFields, q(c.skills.join(" | "))].join(",");
    });
    const csv = "\uFEFF" + [headers.join(","), ...rows].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${baseFilename}_${dateTag()}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ── Excel export ──────────────────────────────────────────────────────────────
export async function exportJobExcel({ job, candidates, scores }: {
    job: JobProfile; candidates: Candidate[]; scores: MatchResult[];
}): Promise<void> {
    const ExcelJS = (await import("exceljs")).default;
    const wb = new ExcelJS.Workbook();
    wb.creator = "RecruitAI";
    wb.created = new Date();

    const scoreMap = new Map<string, MatchResult>();
    for (const s of scores) scoreMap.set(s.candidate_id, s);

    const sorted = candidates
        .filter(c => scoreMap.has(c.id))
        .sort((a, b) => scoreMap.get(b.id)!.overall_score - scoreMap.get(a.id)!.overall_score);

    const now = new Date();
    const dateStr = now.toLocaleDateString("es-PE", { day: "2-digit", month: "long", year: "numeric" });
    const TOTAL_COLS = 8;

    // ── Weight labels ─────────────────────────────────────────────────────────
    const DW: Record<string, number> = { skills: 0.40, experience: 0.35, education: 0.25 };
    const wMap: Record<string, number> = {};
    for (const d of (job.scoring_config ?? [])) wMap[d.dimension] = d.weight;
    const wS = Math.round((wMap.skills ?? DW.skills) * 100);
    const wE = Math.round((wMap.experience ?? DW.experience) * 100);
    const wU = Math.round((wMap.education ?? DW.education) * 100);

    const top    = sorted.filter(c => ["Altamente recomendado","Buena opción"].includes(scoreMap.get(c.id)?.recommendation ?? ""));
    const avgSc  = scores.length ? Math.round(scores.reduce((s, m) => s + m.overall_score, 0) / scores.length) : 0;

    // ═══════════════════════════════════════════════════════════════════════════
    // SHEET 1 — RESUMEN EJECUTIVO
    // ═══════════════════════════════════════════════════════════════════════════
    const ws0 = wb.addWorksheet("Resumen Ejecutivo");
    ws0.columns = [
        { width: 28 }, { width: 32 }, { width: 14 }, { width: 26 }, { width: 18 }, { width: 18 },
    ];

    // Title
    ws0.mergeCells("A1:F1");
    const titleCell = ws0.getCell("A1");
    titleCell.value = "RecruitAI — Informe de Selección de Personal";
    titleCell.font  = { bold: true, size: 16, color: { argb: C.fWhite }, name: "Calibri" };
    titleCell.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: C.titleBlue } };
    titleCell.alignment = { horizontal: "center", vertical: "middle" };
    ws0.getRow(1).height = 32;

    // Job info block
    const infoData: [string, string][] = [
        ["Puesto", job.title],
        ["Área / Departamento", job.department || "—"],
        ["Modalidad", job.work_modality === "remote" ? "Remoto" : job.work_modality === "hybrid" ? "Híbrido" : job.work_modality === "onsite" ? "Presencial" : "—"],
        ["Experiencia mínima requerida", `${job.min_experience_years} años`],
        ["Fecha del informe", dateStr],
    ];
    let row = 3;
    for (const [label, val] of infoData) {
        ws0.mergeCells(row, 2, row, 3);
        const lc = ws0.getCell(row, 1);
        const vc = ws0.getCell(row, 2);
        lc.value = label;
        vc.value = val;
        lc.font = { bold: true, size: 10, color: { argb: C.fGray }, name: "Calibri" };
        vc.font = { size: 10, color: { argb: C.fDark }, name: "Calibri" };
        lc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: C.altRow } };
        vc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: C.white } };
        lc.alignment = { vertical: "middle", indent: 1 };
        vc.alignment = { vertical: "middle", indent: 1 };
        lc.border = thin("FFCBD5E1");
        vc.border = thin("FFCBD5E1");
        ws0.getRow(row).height = 18;
        row++;
    }
    row++; // blank row

    // KPI cards — 4 metrics in one row
    sectionLabel(ws0, row, "Resumen de Evaluación", 6);
    row++;

    type KPI = { label: string; value: string | number; bg: string; bdr: string; font: string };
    const kpis: KPI[] = [
        { label: "CVs Procesados",        value: candidates.length, bg: C.kpiBlue,  bdr: C.kpiBlueBdr,  font: C.fBlue  },
        { label: "Evaluados con IA",       value: scores.length,     bg: C.kpiBlue,  bdr: C.kpiBlueBdr,  font: C.fBlue  },
        { label: "Puntaje Promedio",       value: `${avgSc}%`,       bg: C.kpiGreen, bdr: C.kpiGreenBdr, font: C.fGreen },
        { label: "Recomendados Entrevista",value: top.length,        bg: C.kpiGreen, bdr: C.kpiGreenBdr, font: C.fGreen },
    ];
    // Value row
    for (let i = 0; i < kpis.length; i++) {
        const k = kpis[i];
        ws0.mergeCells(row, i + 1, row, i + 1);
        const vc = ws0.getCell(row, i + 1);
        vc.value = k.value;
        vc.font  = { bold: true, size: 18, color: { argb: k.font }, name: "Calibri" };
        vc.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: k.bg } };
        vc.alignment = { horizontal: "center", vertical: "middle" };
        vc.border = { top: { style: "medium", color: { argb: k.bdr } },
                      bottom: { style: "thin", color: { argb: k.bdr } },
                      left: { style: "thin", color: { argb: k.bdr } },
                      right: { style: "thin", color: { argb: k.bdr } } };
    }
    ws0.getRow(row).height = 36;
    row++;
    // Label row below values
    for (let i = 0; i < kpis.length; i++) {
        const k = kpis[i];
        const lc = ws0.getCell(row, i + 1);
        lc.value = k.label;
        lc.font  = { size: 9, color: { argb: k.font }, name: "Calibri" };
        lc.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: k.bg } };
        lc.alignment = { horizontal: "center", vertical: "top", wrapText: true };
        lc.border = { top: { style: "thin", color: { argb: k.bdr } },
                      bottom: { style: "medium", color: { argb: k.bdr } },
                      left: { style: "thin", color: { argb: k.bdr } },
                      right: { style: "thin", color: { argb: k.bdr } } };
    }
    ws0.getRow(row).height = 18;
    row += 2;

    // Scoring weights
    sectionLabel(ws0, row, "Criterios de Evaluación (pesos del análisis IA)", 6);
    row++;
    const criteria: [string, string, string][] = [
        ["Skills técnicos y blandos", `${wS}%`, C.scoreMid],
        ["Experiencia laboral relevante", `${wE}%`, C.scoreHigh],
        ["Formación académica", `${wU}%`, C.scoreNone],
    ];
    for (const [label, pct, bg] of criteria) {
        ws0.mergeCells(row, 2, row, 3);
        const lc = ws0.getCell(row, 1);
        const vc = ws0.getCell(row, 2);
        lc.value = label;
        vc.value = pct;
        lc.font = { size: 10, color: { argb: C.fDark }, name: "Calibri" };
        vc.font = { bold: true, size: 10, color: { argb: C.fBlue }, name: "Calibri" };
        lc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: C.white } };
        vc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: bg } };
        lc.alignment = { vertical: "middle", indent: 1 };
        vc.alignment = { horizontal: "center", vertical: "middle" };
        lc.border = thin("FFCBD5E1");
        vc.border = thin("FFCBD5E1");
        ws0.getRow(row).height = 18;
        row++;
    }
    row++;

    // Top candidates table
    sectionLabel(ws0, row, `Top ${Math.min(top.length, 10)} Candidatos Recomendados`, 6);
    row++;
    const tHeaders = ["#", "Nombre", "Score", "Recomendación", "Email", "Teléfono"];
    tHeaders.forEach((h, i) => { ws0.getCell(row, i + 1).value = h; });
    applyHeaderRow(ws0.getRow(row), C.headerMid, 6);
    row++;
    top.slice(0, 10).forEach((c, i) => {
        const sc = scoreMap.get(c.id)!;
        const vals = [i + 1, c.full_name, `${Math.round(sc.overall_score)}%`, sc.recommendation, c.email ?? "—", c.phone ?? "—"];
        vals.forEach((v, ci) => { ws0.getCell(row, ci + 1).value = v; });
        const rs = recStyle(sc.recommendation);
        applyDataRow(ws0.getRow(row), i % 2 === 0 ? C.white : C.altRow, C.fDark, 6);
        // Color the recommendation cell
        const recCell = ws0.getCell(row, 4);
        recCell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: rs.bg } };
        recCell.font = { bold: true, size: 10, color: { argb: rs.font }, name: "Calibri" };
        recCell.alignment = { horizontal: "center", vertical: "middle" };
        // Bold score
        const scCell = ws0.getCell(row, 3);
        const sv = scoreStyle(sc.overall_score);
        scCell.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: sv.bg } };
        scCell.font  = { bold: true, size: 10, color: { argb: sv.font }, name: "Calibri" };
        scCell.alignment = { horizontal: "center", vertical: "middle" };
        row++;
    });

    // ═══════════════════════════════════════════════════════════════════════════
    // SHEET 2 — TODOS LOS CANDIDATOS
    // ═══════════════════════════════════════════════════════════════════════════
    const ws1 = wb.addWorksheet("Todos los Candidatos");
    ws1.columns = [
        { width: 28 }, { width: 28 }, { width: 16 }, { width: 12 },
        { width: 18 }, { width: 12 }, { width: 26 }, { width: 40 },
    ];
    const h1 = ["Nombre", "Email", "Teléfono", "Exp. (años)", "Etapa", "Score IA (%)", "Recomendación IA", "Habilidades"];
    h1.forEach((v, i) => { ws1.getCell(1, i + 1).value = v; });
    applyHeaderRow(ws1.getRow(1), C.headerDark, h1.length);

    candidates.forEach((c, idx) => {
        const sc = scoreMap.get(c.id);
        const vals = [
            c.full_name, c.email ?? "", c.phone ?? "", c.total_experience_years,
            STATUS_LABELS[c.status] ?? c.status,
            sc ? Math.round(sc.overall_score) : "",
            sc?.recommendation ?? "",
            c.skills.join(", "),
        ];
        const r = idx + 2;
        vals.forEach((v, ci) => { ws1.getCell(r, ci + 1).value = v; });
        const rowBg = idx % 2 === 0 ? C.white : C.altRow;
        applyDataRow(ws1.getRow(r), rowBg, C.fDark, h1.length, true);
        if (sc) {
            // Score cell
            const sv = scoreStyle(Math.round(sc.overall_score));
            const sc1 = ws1.getCell(r, 6);
            sc1.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: sv.bg } };
            sc1.font  = { bold: true, size: 10, color: { argb: sv.font }, name: "Calibri" };
            sc1.alignment = { horizontal: "center", vertical: "middle" };
            // Recommendation cell
            const rs = recStyle(sc.recommendation);
            const rc1 = ws1.getCell(r, 7);
            rc1.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: rs.bg } };
            rc1.font  = { bold: true, size: 10, color: { argb: rs.font }, name: "Calibri" };
            rc1.alignment = { horizontal: "center", vertical: "middle" };
        }
    });
    ws1.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: h1.length } };
    ws1.views = [{ state: "frozen", ySplit: 1 }];

    // ═══════════════════════════════════════════════════════════════════════════
    // SHEET 3 — ANÁLISIS IA
    // ═══════════════════════════════════════════════════════════════════════════
    const ws2 = wb.addWorksheet("Análisis IA");
    ws2.columns = [
        { width: 28 }, { width: 28 }, { width: 16 }, { width: 14 },
        { width: 16 }, { width: 16 }, { width: 14 },
        { width: 26 }, { width: 28 }, { width: 22 }, { width: 55 },
    ];
    const h2 = [
        "Nombre", "Email", "Teléfono", "Score Global",
        `Skills (${wS}%)`, `Experiencia (${wE}%)`, `Educación (${wU}%)`,
        "Recomendación", "Habilidades Faltantes", "Habilidades Bonus", "Resumen IA",
    ];
    h2.forEach((v, i) => { ws2.getCell(1, i + 1).value = v; });
    applyHeaderRow(ws2.getRow(1), C.headerDark, h2.length);

    sorted.forEach((c, idx) => {
        const sc = scoreMap.get(c.id)!;
        const vals = [
            c.full_name, c.email ?? "", c.phone ?? "",
            Math.round(sc.overall_score),
            Math.round(sc.skills_score), Math.round(sc.experience_score), Math.round(sc.education_score),
            sc.recommendation, sc.missing_skills.join(", "), sc.bonus_skills.join(", "), sc.explanation,
        ];
        const r = idx + 2;
        vals.forEach((v, ci) => { ws2.getCell(r, ci + 1).value = v; });
        applyDataRow(ws2.getRow(r), idx % 2 === 0 ? C.white : C.altRow, C.fDark, h2.length, true);
        // Color score cells (cols 4-7)
        [sc.overall_score, sc.skills_score, sc.experience_score, sc.education_score].forEach((v, ci) => {
            const sv = scoreStyle(Math.round(v));
            const cell = ws2.getCell(r, ci + 4);
            cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: sv.bg } };
            cell.font = { bold: true, size: 10, color: { argb: sv.font }, name: "Calibri" };
            cell.alignment = { horizontal: "center", vertical: "middle" };
        });
        // Recommendation
        const rs = recStyle(sc.recommendation);
        const rc2 = ws2.getCell(r, 8);
        rc2.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: rs.bg } };
        rc2.font  = { bold: true, size: 10, color: { argb: rs.font }, name: "Calibri" };
        rc2.alignment = { horizontal: "center", vertical: "middle" };
    });
    ws2.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: h2.length } };
    ws2.views = [{ state: "frozen", ySplit: 1 }];

    // ═══════════════════════════════════════════════════════════════════════════
    // SHEET 4 — TOP 5 DETALLE
    // ═══════════════════════════════════════════════════════════════════════════
    const ws3 = wb.addWorksheet("Top 5");
    ws3.columns = [
        { width: 24 }, { width: 40 }, { width: 14 }, { width: 28 },
        { width: 14 }, { width: 18 }, { width: 12 }, { width: 18 },
    ];

    let r3 = 1;
    // Sheet title
    ws3.mergeCells(r3, 1, r3, 8);
    const t3 = ws3.getCell(r3, 1);
    t3.value = `${job.title} — Top 5 Candidatos | ${dateStr}`;
    t3.font  = { bold: true, size: 13, color: { argb: C.fWhite }, name: "Calibri" };
    t3.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: C.titleBlue } };
    t3.alignment = { horizontal: "center", vertical: "middle" };
    ws3.getRow(r3).height = 26;
    r3 += 2;

    const top5 = sorted.slice(0, 5);
    const TIPO_LABEL: Record<string, string> = {
        validar_logro: "Validar logro", explorar_brecha: "Explorar brecha", validar_inferencia: "Validar inferencia",
    };

    top5.forEach((c, i) => {
        const sc = scoreMap.get(c.id)!;
        const rs = recStyle(sc.recommendation);

        // Candidate name header
        ws3.mergeCells(r3, 1, r3, 8);
        const nameCell = ws3.getCell(r3, 1);
        nameCell.value = `#${i + 1}  ${c.full_name}`;
        nameCell.font  = { bold: true, size: 13, color: { argb: rs.font }, name: "Calibri" };
        nameCell.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: rs.bg } };
        nameCell.alignment = { horizontal: "left", vertical: "middle", indent: 1 };
        nameCell.border = { top: { style: "medium", color: { argb: rs.font } },
                            bottom: { style: "thin", color: { argb: rs.font } },
                            left: { style: "medium", color: { argb: rs.font } },
                            right: { style: "medium", color: { argb: rs.font } } };
        ws3.getRow(r3).height = 22;
        r3++;

        // Contact row
        const contactData: [string, string, string, string][] = [
            ["Email", c.email ?? "—", "Teléfono", c.phone ?? "—"],
        ];
        for (const [l1, v1, l2, v2] of contactData) {
            ws3.mergeCells(r3, 2, r3, 3); ws3.mergeCells(r3, 4, r3, 5);
            ws3.mergeCells(r3, 6, r3, 7);
            const cells: [number, string | number, boolean][] = [[1,l1,true],[2,v1,false],[4,l2,true],[6,v2,false]];
            for (const [col, val, isBold] of cells) {
                const cc = ws3.getCell(r3, col);
                cc.value = val; cc.border = thin("FFCBD5E1");
                cc.font  = { bold: isBold, size: 10, color: { argb: isBold ? C.fGray : C.fDark }, name: "Calibri" };
                cc.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: C.altRow } };
                cc.alignment = { vertical: "middle", indent: 1 };
            }
            ws3.getRow(r3).height = 16;
            r3++;
        }

        // Score row
        ws3.mergeCells(r3, 1, r3, 8);
        const scoreHeaders = [`Score Global: ${Math.round(sc.overall_score)}%`,
            `  Skills (${wS}%): ${Math.round(sc.skills_score)}%`,
            `  Exp. (${wE}%): ${Math.round(sc.experience_score)}%`,
            `  Edu. (${wU}%): ${Math.round(sc.education_score)}%`,
        ].join("   |   ");
        const scRow = ws3.getCell(r3, 1);
        scRow.value = scoreHeaders;
        scRow.font  = { bold: true, size: 10, color: { argb: rs.font }, name: "Calibri" };
        scRow.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: rs.bg } };
        scRow.alignment = { horizontal: "left", vertical: "middle", indent: 1 };
        scRow.border = thin(rs.font);
        ws3.getRow(r3).height = 16;
        r3++;

        // Recommendation + AI summary
        const detailRows: [string, string][] = [
            ["Recomendación", sc.recommendation],
            ["Resumen IA", sc.explanation],
        ];
        if (sc.missing_skills.length > 0) detailRows.push(["Habilidades Faltantes", sc.missing_skills.join(", ")]);
        if (sc.bonus_skills.length > 0)   detailRows.push(["Habilidades Bonus", sc.bonus_skills.join(", ")]);

        for (const [label, val] of detailRows) {
            ws3.mergeCells(r3, 2, r3, 8);
            const lc = ws3.getCell(r3, 1);
            const vc = ws3.getCell(r3, 2);
            lc.value = label; vc.value = val;
            lc.font = { bold: true, size: 10, color: { argb: C.fGray }, name: "Calibri" };
            vc.font = { size: 10, color: { argb: C.fDark }, name: "Calibri" };
            lc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: C.altRow } };
            vc.fill = { type: "pattern", pattern: "solid", fgColor: { argb: C.white } };
            lc.alignment = { vertical: "top", indent: 1 };
            vc.alignment = { vertical: "top", wrapText: true };
            lc.border = thin("FFCBD5E1"); vc.border = thin("FFCBD5E1");
            ws3.getRow(r3).height = label === "Resumen IA" ? 36 : 18;
            r3++;
        }

        // Interview guide
        const guia = sc.guia_entrevista ?? [];
        if (guia.length > 0) {
            // Guide header
            ws3.mergeCells(r3, 1, r3, 8);
            const gh = ws3.getCell(r3, 1);
            gh.value = "Guía de Entrevista";
            gh.font  = { bold: true, size: 10, color: { argb: C.fWhite }, name: "Calibri" };
            gh.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: C.headerMid } };
            gh.alignment = { horizontal: "left", vertical: "middle", indent: 1 };
            gh.border = thin(C.headerMid);
            ws3.getRow(r3).height = 18;
            r3++;

            guia.forEach((q, qi) => {
                ws3.mergeCells(r3, 2, r3, 8);
                const qLabel = ws3.getCell(r3, 1);
                const qText  = ws3.getCell(r3, 2);
                qLabel.value = `P${qi + 1}. ${TIPO_LABEL[q.tipo] ?? q.tipo}`;
                qText.value  = q.pregunta;
                qLabel.font  = { bold: true, size: 9, color: { argb: C.fBlue }, name: "Calibri" };
                qText.font   = { size: 10, color: { argb: C.fDark }, name: "Calibri" };
                qLabel.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: C.kpiBlue } };
                qText.fill   = { type: "pattern", pattern: "solid", fgColor: { argb: C.white } };
                qLabel.alignment = { vertical: "top", wrapText: true, indent: 1 };
                qText.alignment  = { vertical: "top", wrapText: true };
                qLabel.border = thin(C.kpiBlueBdr); qText.border = thin(C.kpiBlueBdr);
                ws3.getRow(r3).height = 30;
                r3++;
            });
        }
        r3 += 2; // spacing between candidates
    });

    // ── Download ──────────────────────────────────────────────────────────────
    const safeTitle = job.title.replace(/[^\w\s-]/g, "").trim().slice(0, 30).replace(/\s+/g, "_");
    const buffer = await wb.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `RecruitAI_${safeTitle}_${dateTag()}.xlsx`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
