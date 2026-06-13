"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { candidatesApi, notesApi, CandidateDetail as CandidateDetailType, CandidateNote } from "@/lib/api";
import ExperienceEditor from "./ExperienceEditor";

const STATUS_LABELS: Record<string, string> = {
    new: "Nuevo", screening: "En Revisión", shortlisted: "Preseleccionado",
    interview: "Entrevista", offer: "Oferta", hired: "Contratado", rejected: "Descartado",
};
const STATUS_STYLES: Record<string, string> = {
    new: "bg-slate-500/20 text-slate-400",
    screening: "bg-indigo-500/20 text-indigo-400",
    shortlisted: "bg-violet-500/20 text-violet-400",
    interview: "bg-amber-500/20 text-amber-400",
    offer: "bg-emerald-500/20 text-emerald-400",
    hired: "bg-green-500/20 text-green-400",
    rejected: "bg-red-500/20 text-red-400",
};

const NOTE_TYPE_LABELS: Record<string, string> = {
    general: "General", interview: "Entrevista", feedback: "Feedback", status_change: "Estado",
};
const NOTE_BORDER: Record<string, string> = {
    status_change: "border-l-amber-500 bg-amber-50/50 dark:bg-amber-900/10",
    interview: "border-l-violet-500 bg-violet-50/50 dark:bg-violet-900/10",
    feedback: "border-l-emerald-500 bg-emerald-50/50 dark:bg-emerald-900/10",
    general: "border-l-blue-500 bg-blue-50/50 dark:bg-blue-900/10",
};

function formatDate(d: string | null | undefined): string {
    if (!d || d === "null") return "";
    const m = d.match(/^(\d{4})-(\d{2})/);
    if (!m) return d;
    const months = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
    return `${months[parseInt(m[2], 10) - 1]} ${m[1]}`;
}

const CandidateDetailPage: React.FC = () => {
    const params = useParams();
    const router = useRouter();
    const candidateId = params.id as string;

    const [candidate, setCandidate] = useState<CandidateDetailType | null>(null);
    const [notes, setNotes] = useState<CandidateNote[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [rating, setRating] = useState(0);
    const [hoverRating, setHoverRating] = useState(0);
    const [notesOpen, setNotesOpen] = useState(false);
    const [newNote, setNewNote] = useState("");
    const [noteType, setNoteType] = useState("general");
    const [submittingNote, setSubmittingNote] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [loadingFile, setLoadingFile] = useState<"preview" | "download" | null>(null);

    // Inline edit for contact data (used when LLM extraction missed something)
    const [editingContact, setEditingContact] = useState(false);
    const [contactDraft, setContactDraft] = useState({ full_name: "", email: "", phone: "", linkedin: "", github: "" });
    const [savingContact, setSavingContact] = useState(false);

    // Modal edit for the full experience list
    const [editingExperience, setEditingExperience] = useState(false);

    useEffect(() => {
        if (!candidateId) return;
        (async () => {
            try {
                setLoading(true);
                const [candRes, notesRes] = await Promise.all([
                    candidatesApi.get(candidateId),
                    notesApi.list(candidateId).catch(() => ({ data: { items: [] } })),
                ]);
                setCandidate(candRes.data);
                setNotes(notesRes.data.items || []);
                setRating((candRes.data as any).rating || 0);
            } catch {
                setError("No se pudo cargar el candidato");
            } finally {
                setLoading(false);
            }
        })();
    }, [candidateId]);

    const handleRatingChange = async (r: number) => {
        try { await notesApi.updateRating(candidateId, r); setRating(r); } catch {}
    };

    const handleAddNote = async () => {
        if (!newNote.trim()) return;
        try {
            setSubmittingNote(true);
            const res = await notesApi.create(candidateId, { content: newNote, note_type: noteType });
            setNotes([res.data, ...notes]);
            setNewNote("");
        } catch {} finally { setSubmittingNote(false); }
    };

    const handleDelete = async () => {
        try {
            setDeleting(true);
            await candidatesApi.delete(candidateId);
            router.push("/candidates");
        } catch { setDeleting(false); }
    };

    const openContactEdit = () => {
        if (!candidate) return;
        setContactDraft({
            full_name: candidate.full_name || "",
            email: candidate.email || "",
            phone: candidate.phone || "",
            linkedin: candidate.linkedin || "",
            github: candidate.github || "",
        });
        setEditingContact(true);
    };

    const saveContactEdit = async () => {
        if (!candidate || !contactDraft.full_name.trim()) return;
        try {
            setSavingContact(true);
            const res = await candidatesApi.update(candidateId, {
                full_name: contactDraft.full_name.trim(),
                email: contactDraft.email.trim() || null,
                phone: contactDraft.phone.trim() || null,
                linkedin: contactDraft.linkedin.trim() || null,
                github: contactDraft.github.trim() || null,
            });
            setCandidate({ ...candidate, ...res.data });
            setEditingContact(false);
        } catch {
            alert("No se pudo guardar. Intenta de nuevo.");
        } finally {
            setSavingContact(false);
        }
    };

    const handleOpenFile = async (disposition: "preview" | "download") => {
        setLoadingFile(disposition);
        try {
            const res = await candidatesApi.getFile(candidateId, disposition === "preview" ? "preview" : "download");
            const blob = new Blob([res.data], { type: res.headers["content-type"] || "application/octet-stream" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            if (disposition === "download") {
                const cd = res.headers["content-disposition"] || "";
                const match = cd.match(/filename="?([^"]+)"?/);
                a.download = match ? match[1] : "cv.pdf";
            } else {
                a.target = "_blank";
                a.rel = "noopener noreferrer";
            }
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 10000);
        } catch (err: any) {
            alert(err?.response?.status === 404
                ? "El CV aún no está disponible."
                : "Error al abrir el archivo. Intenta de nuevo.");
        } finally { setLoadingFile(null); }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
            <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
            <p className="text-slate-400">Cargando perfil del candidato...</p>
        </div>
    );

    if (error || !candidate) return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
            <span className="material-symbols-outlined text-[64px] text-red-400">error</span>
            <p className="text-slate-500">{error || "Candidato no encontrado"}</p>
            <Link href="/candidates" className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg">
                <span className="material-symbols-outlined text-[20px]">arrow_back</span>Volver
            </Link>
        </div>
    );

    const initials = candidate.full_name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();
    const educacion = (candidate.education || []).filter((e: any) => (e.education_type || "educacion") === "educacion");
    const certificaciones = (candidate.education || []).filter((e: any) => e.education_type === "certificacion");
    const idiomas = candidate.idiomas || [];

    return (
        <>
            {/* Back */}
            <div className="mb-5">
                <button onClick={() => router.back()}
                    className="flex items-center gap-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors text-sm">
                    <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                    Volver
                </button>
            </div>

            {/* ── Header ─────────────────────────────────────────────────────────── */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 mb-5 shadow-sm">
                <div className="flex flex-col md:flex-row gap-5">
                    {/* Avatar */}
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center flex-shrink-0">
                        <span className="text-2xl font-bold text-white">{initials}</span>
                    </div>

                    <div className="flex-1 min-w-0">
                        {/* Name + status + edit */}
                        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900 dark:text-white leading-tight">{candidate.full_name}</h1>
                                <div className="flex flex-wrap items-center gap-3 mt-1.5">
                                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLES[candidate.status] || STATUS_STYLES.new}`}>
                                        {STATUS_LABELS[candidate.status] || candidate.status}
                                    </span>
                                    {/* Star rating */}
                                    <div className="flex items-center gap-0.5">
                                        {[1,2,3,4,5].map(star => (
                                            <button key={star} onClick={() => handleRatingChange(star)}
                                                onMouseEnter={() => setHoverRating(star)}
                                                onMouseLeave={() => setHoverRating(0)}
                                                className="p-0.5">
                                                <span className={`material-symbols-outlined text-[20px] transition-colors ${star <= (hoverRating || rating) ? "text-amber-400" : "text-slate-300 dark:text-slate-600"}`}>star</span>
                                            </button>
                                        ))}
                                        {rating === 0 && <span className="text-[11px] text-slate-400 ml-1">Sin calificar</span>}
                                    </div>
                                </div>
                            </div>

                            {/* CV buttons */}
                            <div className="flex gap-2 flex-shrink-0">
                                <button onClick={() => handleOpenFile("preview")} disabled={loadingFile !== null}
                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 text-sm font-medium disabled:opacity-50 transition-colors">
                                    <span className="material-symbols-outlined text-[16px]">{loadingFile === "preview" ? "sync" : "visibility"}</span>
                                    {loadingFile === "preview" ? "Cargando..." : "Ver CV"}
                                </button>
                                <button onClick={() => handleOpenFile("download")} disabled={loadingFile !== null}
                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 text-sm font-medium disabled:opacity-50 transition-colors">
                                    <span className="material-symbols-outlined text-[16px]">{loadingFile === "download" ? "sync" : "download"}</span>
                                    {loadingFile === "download" ? "..." : "Descargar"}
                                </button>
                            </div>
                        </div>

                        {/* Contact */}
                        {editingContact ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                                <input
                                    value={contactDraft.full_name}
                                    onChange={e => setContactDraft({ ...contactDraft, full_name: e.target.value })}
                                    placeholder="Nombre completo"
                                    className="px-3 py-1.5 text-sm rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:outline-none focus:border-primary"
                                />
                                <input
                                    value={contactDraft.email}
                                    onChange={e => setContactDraft({ ...contactDraft, email: e.target.value })}
                                    placeholder="Email"
                                    className="px-3 py-1.5 text-sm rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:outline-none focus:border-primary"
                                />
                                <input
                                    value={contactDraft.phone}
                                    onChange={e => setContactDraft({ ...contactDraft, phone: e.target.value })}
                                    placeholder="Teléfono"
                                    className="px-3 py-1.5 text-sm rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:outline-none focus:border-primary"
                                />
                                <input
                                    value={contactDraft.linkedin}
                                    onChange={e => setContactDraft({ ...contactDraft, linkedin: e.target.value })}
                                    placeholder="LinkedIn (URL)"
                                    className="px-3 py-1.5 text-sm rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:outline-none focus:border-primary"
                                />
                                <input
                                    value={contactDraft.github}
                                    onChange={e => setContactDraft({ ...contactDraft, github: e.target.value })}
                                    placeholder="GitHub (URL)"
                                    className="px-3 py-1.5 text-sm rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:outline-none focus:border-primary"
                                />
                                <div className="sm:col-span-2 flex justify-end gap-2 pt-1">
                                    <button
                                        onClick={() => setEditingContact(false)}
                                        disabled={savingContact}
                                        className="px-3 py-1.5 text-xs font-medium rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={saveContactEdit}
                                        disabled={savingContact || !contactDraft.full_name.trim()}
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-primary text-white hover:bg-blue-600 disabled:opacity-50"
                                    >
                                        <span className="material-symbols-outlined text-[14px]">{savingContact ? "sync" : "save"}</span>
                                        {savingContact ? "Guardando..." : "Guardar"}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500 mb-4">
                                <span className="flex items-center gap-1.5">
                                    <span className="material-symbols-outlined text-[16px]">mail</span>
                                    {candidate.email || <span className="italic text-slate-400">sin email</span>}
                                </span>
                                <span className="flex items-center gap-1.5">
                                    <span className="material-symbols-outlined text-[16px]">phone</span>
                                    {candidate.phone || <span className="italic text-slate-400">sin teléfono</span>}
                                </span>
                                {candidate.linkedin ? (
                                    <a href={candidate.linkedin.startsWith("http") ? candidate.linkedin : `https://${candidate.linkedin}`}
                                        target="_blank" rel="noopener noreferrer"
                                        className="flex items-center gap-1.5 text-primary hover:underline">
                                        <span className="material-symbols-outlined text-[16px]">link</span>LinkedIn
                                    </a>
                                ) : (
                                    <span className="flex items-center gap-1.5 italic text-slate-400">
                                        <span className="material-symbols-outlined text-[16px]">link</span>sin LinkedIn
                                    </span>
                                )}
                                {candidate.github && (
                                    <a href={candidate.github.startsWith("http") ? candidate.github : `https://${candidate.github}`}
                                        target="_blank" rel="noopener noreferrer"
                                        className="flex items-center gap-1.5 text-primary hover:underline">
                                        <span className="material-symbols-outlined text-[16px]">code</span>GitHub
                                    </a>
                                )}
                                <button
                                    onClick={openContactEdit}
                                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-primary transition-colors"
                                    title="Editar datos de contacto"
                                >
                                    <span className="material-symbols-outlined text-[14px]">edit</span>
                                    Editar
                                </button>
                            </div>
                        )}

                        {/* Stats bar */}
                        <div className="flex flex-wrap gap-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                            {[
                                { label: "Experiencia", value: `${candidate.total_experience_years} años`, icon: "work_history" },
                                { label: "Habilidades", value: `${candidate.skills?.length || 0}`, icon: "psychology" },
                                { label: "Posiciones", value: `${candidate.experience?.length || 0}`, icon: "business_center" },
                                { label: "Idiomas", value: `${idiomas.length}`, icon: "language" },
                            ].map(({ label, value, icon }) => (
                                <div key={label} className="flex items-center gap-2">
                                    <span className={`material-symbols-outlined text-[16px] text-slate-400`}>{icon}</span>
                                    <div>
                                        <p className="text-[10px] text-slate-400 uppercase tracking-wider leading-none">{label}</p>
                                        <p className="text-base font-bold text-slate-900 dark:text-white leading-tight">{value}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Main grid ──────────────────────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                {/* Left: Skills + Notes */}
                <div className="lg:col-span-1 space-y-5">

                    {/* Skills */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2 uppercase tracking-wider">
                            <span className="material-symbols-outlined text-primary text-[18px]">psychology</span>
                            Habilidades
                        </h3>
                        {candidate.skills?.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                                {candidate.skills.map((skill, i) => (
                                    <span key={i} className="px-2.5 py-1 rounded-lg bg-primary/10 text-primary text-xs font-medium">{skill}</span>
                                ))}
                            </div>
                        ) : (
                            <p className="text-slate-400 text-sm">No se detectaron habilidades</p>
                        )}
                    </div>

                    {/* Notes — collapsible */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
                        <button
                            onClick={() => setNotesOpen(o => !o)}
                            className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
                        >
                            <span className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                <span className="material-symbols-outlined text-blue-500 text-[18px]">edit_note</span>
                                Notas
                                {notes.length > 0 && (
                                    <span className="px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-500 text-[10px] font-bold">{notes.length}</span>
                                )}
                            </span>
                            <span className="material-symbols-outlined text-[18px] text-slate-400">{notesOpen ? "expand_less" : "expand_more"}</span>
                        </button>

                        {notesOpen && (
                            <div className="px-5 pb-5 space-y-4 border-t border-slate-100 dark:border-slate-700 pt-4">
                                {/* Add note form */}
                                <div className="space-y-2">
                                    <select value={noteType} onChange={e => setNoteType(e.target.value)}
                                        className="w-full px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-200">
                                        <option value="general">Nota General</option>
                                        <option value="interview">Entrevista</option>
                                        <option value="feedback">Feedback</option>
                                    </select>
                                    <textarea value={newNote} onChange={e => setNewNote(e.target.value)}
                                        placeholder="Escribe una nota..." rows={2}
                                        className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm resize-none" />
                                    <button onClick={handleAddNote} disabled={!newNote.trim() || submittingNote}
                                        className="w-full flex items-center justify-center gap-1.5 py-1.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors">
                                        <span className="material-symbols-outlined text-[16px]">{submittingNote ? "sync" : "add"}</span>
                                        Guardar
                                    </button>
                                </div>

                                {/* History */}
                                {notes.length > 0 && (
                                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                                        {notes.map(note => (
                                            <div key={note.id} className={`p-3 rounded-lg border-l-4 ${NOTE_BORDER[note.note_type] || NOTE_BORDER.general}`}>
                                                <div className="flex items-center justify-between gap-2 mb-1">
                                                    <span className="text-[10px] font-bold text-slate-500 uppercase">{NOTE_TYPE_LABELS[note.note_type]}</span>
                                                    <span className="text-[10px] text-slate-400">
                                                        {new Date(note.created_at).toLocaleDateString("es-PE", { day: "2-digit", month: "short" })}
                                                    </span>
                                                </div>
                                                <p className="text-xs text-slate-700 dark:text-slate-300">{note.content}</p>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {notes.length === 0 && (
                                    <p className="text-xs text-slate-400 text-center py-2">Sin notas aún</p>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Delete */}
                    <button onClick={() => setShowDeleteModal(true)}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 text-sm font-medium hover:border-red-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors">
                        <span className="material-symbols-outlined text-[16px]">delete</span>
                        Eliminar candidato
                    </button>
                </div>

                {/* Right: Experiencia, Formación, Certificaciones, Idiomas */}
                <div className="lg:col-span-2 space-y-5">

                    {/* Experiencia Laboral */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 uppercase tracking-wider">
                                <span className="material-symbols-outlined text-emerald-500 text-[18px]">work</span>
                                Experiencia Laboral
                            </h3>
                            <button
                                onClick={() => setEditingExperience(true)}
                                className="flex items-center gap-1 text-xs text-slate-400 hover:text-primary transition-colors"
                                title="Editar experiencia laboral"
                            >
                                <span className="material-symbols-outlined text-[14px]">edit</span>
                                Editar
                            </button>
                        </div>
                        {candidate.experience?.length > 0 ? (
                            <div className="relative pl-6 border-l-2 border-slate-200 dark:border-slate-700 space-y-6">
                                {candidate.experience.map((exp, i) => {
                                    const descLines = (exp.description || "").split("\n");
                                    const periodoLine = descLines.find(l => l.startsWith("Periodo:"));
                                    const periodoRaw = periodoLine ? periodoLine.replace("Periodo: ", "").trim() : null;
                                    const periodo = (periodoRaw && periodoRaw !== "null" && periodoRaw !== "-" && periodoRaw !== " - ") ? periodoRaw : null;
                                    const logros = descLines.filter(l => !l.startsWith("Periodo:") && l.trim());
                                    const start = exp.start_date ? formatDate(exp.start_date) : null;
                                    const end = exp.is_current ? "Presente" : (exp.end_date ? formatDate(exp.end_date) : "Presente");
                                    const dateDisplay = periodo || (start ? `${start} - ${end}` : end);

                                    return (
                                        <div key={i} className="relative">
                                            <div className={`absolute -left-[29px] w-4 h-4 rounded-full border-4 border-white dark:border-slate-800 ${exp.is_current ? "bg-emerald-500" : "bg-primary"}`} />
                                            <h4 className="font-bold text-slate-900 dark:text-white">{exp.title}</h4>
                                            <p className="text-primary font-medium text-sm">{exp.company}</p>
                                            <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                                                <span className="material-symbols-outlined text-[14px]">calendar_today</span>
                                                {dateDisplay}
                                                {exp.is_current && (
                                                    <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded-full bg-emerald-500/20 text-emerald-400 font-semibold">Actual</span>
                                                )}
                                            </p>
                                            {logros.length > 0 && (
                                                <ul className="mt-2 space-y-1">
                                                    {logros.map((logro, li) => (
                                                        <li key={li} className="text-slate-600 dark:text-slate-400 text-sm flex items-start gap-1.5">
                                                            <span className="text-emerald-500 mt-0.5 flex-shrink-0">•</span>{logro}
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="text-center py-6 text-slate-400">
                                <span className="material-symbols-outlined text-[28px] block mb-1">work_off</span>
                                <p className="text-sm">No se detectó experiencia laboral</p>
                            </div>
                        )}
                    </div>

                    {/* Formación Académica */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2 uppercase tracking-wider">
                            <span className="material-symbols-outlined text-amber-500 text-[18px]">school</span>
                            Formación Académica
                        </h3>
                        {educacion.length > 0 ? (
                            <div className="space-y-3">
                                {educacion.map((edu: any, i: number) => (
                                    <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                                        <div className="w-9 h-9 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                                            <span className="material-symbols-outlined text-amber-500 text-[18px]">school</span>
                                        </div>
                                        <div>
                                            <h4 className="font-semibold text-slate-900 dark:text-white text-sm">{edu.degree}</h4>
                                            <p className="text-slate-500 text-sm">{edu.institution}</p>
                                            {edu.field_of_study && <p className="text-xs text-slate-400">{edu.field_of_study}</p>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-6 text-slate-400">
                                <span className="material-symbols-outlined text-[28px] block mb-1">school</span>
                                <p className="text-sm">No se detectó formación académica</p>
                            </div>
                        )}
                    </div>

                    {/* Certificaciones */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2 uppercase tracking-wider">
                            <span className="material-symbols-outlined text-purple-500 text-[18px]">workspace_premium</span>
                            Certificaciones
                        </h3>
                        {certificaciones.length > 0 ? (
                            <div className="space-y-2">
                                {certificaciones.map((cert: any, i: number) => (
                                    <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-purple-50/50 dark:bg-purple-900/10 border border-purple-200/50 dark:border-purple-800/30">
                                        <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                                            <span className="material-symbols-outlined text-purple-500 text-[16px]">verified</span>
                                        </div>
                                        <div>
                                            <h4 className="font-medium text-slate-900 dark:text-white text-sm">{cert.degree}</h4>
                                            <p className="text-xs text-slate-500">{cert.institution}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-6 text-slate-400">
                                <span className="material-symbols-outlined text-[28px] block mb-1">workspace_premium</span>
                                <p className="text-sm">No se detectaron certificaciones</p>
                            </div>
                        )}
                    </div>

                    {/* Idiomas */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2 uppercase tracking-wider">
                            <span className="material-symbols-outlined text-teal-500 text-[18px]">language</span>
                            Idiomas
                        </h3>
                        {idiomas.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                                {idiomas.map((lang, i) => (
                                    <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-50 dark:bg-teal-900/20 border border-teal-200/60 dark:border-teal-700/40">
                                        <span className="material-symbols-outlined text-teal-500 text-[16px]">translate</span>
                                        <div>
                                            <span className="text-sm font-semibold text-slate-800 dark:text-white">{lang.idioma}</span>
                                            {lang.nivel && (
                                                <span className="ml-1.5 text-xs text-teal-600 dark:text-teal-400 font-medium">· {lang.nivel}</span>
                                            )}
                                            {lang.certificacion && (
                                                <p className="text-[10px] text-slate-400 mt-0.5">{lang.certificacion}</p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-6 text-slate-400">
                                <span className="material-symbols-outlined text-[28px] block mb-1">language</span>
                                <p className="text-sm">No se detectaron idiomas</p>
                            </div>
                        )}
                    </div>

                </div>
            </div>

            {/* Delete modal */}
            {showDeleteModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-sm shadow-xl">
                        <div className="text-center mb-5">
                            <div className="w-14 h-14 rounded-full bg-red-100 dark:bg-red-900/30 mx-auto mb-3 flex items-center justify-center">
                                <span className="material-symbols-outlined text-red-500 text-[28px]">warning</span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">¿Eliminar Candidato?</h3>
                            <p className="text-sm text-slate-500">Se eliminará permanentemente a <strong>{candidate.full_name}</strong>. Esta acción no se puede deshacer.</p>
                        </div>
                        <div className="flex gap-3">
                            <button onClick={() => setShowDeleteModal(false)} disabled={deleting}
                                className="flex-1 py-2 px-4 rounded-lg border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">
                                Cancelar
                            </button>
                            <button onClick={handleDelete} disabled={deleting}
                                className="flex-1 py-2 px-4 rounded-lg bg-red-500 text-white text-sm font-semibold hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-1.5">
                                <span className="material-symbols-outlined text-[16px]">{deleting ? "sync" : "delete"}</span>
                                {deleting ? "Eliminando..." : "Sí, Eliminar"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {editingExperience && (
                <ExperienceEditor
                    candidateId={candidateId}
                    initial={candidate.experience || []}
                    onClose={() => setEditingExperience(false)}
                    onSaved={updated => setCandidate(updated)}
                />
            )}
        </>
    );
};

export default CandidateDetailPage;
