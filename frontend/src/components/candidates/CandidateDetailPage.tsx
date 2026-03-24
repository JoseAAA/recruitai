"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { candidatesApi, notesApi, CandidateDetail as CandidateDetailType, CandidateNote } from "@/lib/api";

const CandidateDetailPage: React.FC = () => {
    const params = useParams();
    const router = useRouter();
    const candidateId = params.id as string;

    const [candidate, setCandidate] = useState<CandidateDetailType | null>(null);
    const [notes, setNotes] = useState<CandidateNote[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [rating, setRating] = useState<number>(0);
    const [hoverRating, setHoverRating] = useState<number>(0);

    // Note form
    const [newNote, setNewNote] = useState("");
    const [noteType, setNoteType] = useState("general");
    const [submittingNote, setSubmittingNote] = useState(false);
    const [showStatusModal, setShowStatusModal] = useState(false);
    const [statusReason, setStatusReason] = useState("");
    const [selectedStatus, setSelectedStatus] = useState("");


    // Delete confirmation
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [deleting, setDeleting] = useState(false);

    // CV file actions
    const [loadingFile, setLoadingFile] = useState<"preview" | "download" | null>(null);

    useEffect(() => {
        async function fetchData() {
            if (!candidateId) return;

            try {
                setLoading(true);
                const [candidateRes, notesRes] = await Promise.all([
                    candidatesApi.get(candidateId),
                    notesApi.list(candidateId).catch(() => ({ data: { items: [] } })),
                ]);
                setCandidate(candidateRes.data);
                setNotes(notesRes.data.items || []);
                setRating((candidateRes.data as any).rating || 0);
            } catch (err: any) {
                console.error("Failed to fetch candidate:", err);
                setError("No se pudo cargar el candidato");
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, [candidateId]);

    const handleRatingChange = async (newRating: number) => {
        try {
            await notesApi.updateRating(candidateId, newRating);
            setRating(newRating);
        } catch (err) {
            console.error("Failed to update rating:", err);
        }
    };

    const handleAddNote = async () => {
        if (!newNote.trim()) return;

        try {
            setSubmittingNote(true);
            const response = await notesApi.create(candidateId, {
                content: newNote,
                note_type: noteType,
            });
            setNotes([response.data, ...notes]);
            setNewNote("");
        } catch (err) {
            console.error("Failed to add note:", err);
        } finally {
            setSubmittingNote(false);
        }
    };

    const handleStatusChange = async () => {
        if (!selectedStatus) return;

        try {
            await notesApi.updateStatus(candidateId, selectedStatus, statusReason);
            // Reload candidate to get new status
            const response = await candidatesApi.get(candidateId);
            setCandidate(response.data);

            if (statusReason) {
                const notesRes = await notesApi.list(candidateId);
                setNotes(notesRes.data.items || []);
            }

            setShowStatusModal(false);
            setStatusReason("");
        } catch (err) {
            console.error("Failed to update status:", err);
        }
    };

    const handleDelete = async () => {
        try {
            setDeleting(true);
            await candidatesApi.delete(candidateId);
            router.push("/candidates");
        } catch (err) {
            console.error("Failed to delete candidate:", err);
            setDeleting(false);
        }
    };

    const handleOpenFile = async (disposition: "preview" | "download") => {
        setLoadingFile(disposition);
        try {
            const endpoint = disposition === "preview" ? "preview" : "download";
            const response = await candidatesApi.getFile(candidateId, endpoint);
            const blob = new Blob([response.data], {
                type: response.headers["content-type"] || "application/octet-stream",
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            if (disposition === "download") {
                const cd = response.headers["content-disposition"] || "";
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
            const status = err?.response?.status;
            if (status === 404) {
                alert("El CV aún no está disponible. Fue subido antes de activarse el almacenamiento de archivos.");
            } else {
                alert("Error al abrir el archivo. Intenta de nuevo.");
            }
        } finally {
            setLoadingFile(null);
        }
    };

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            new: "bg-emerald-500/20 text-emerald-400",
            reviewed: "bg-blue-500/20 text-blue-400",
            shortlisted: "bg-amber-500/20 text-amber-400",
            interview: "bg-purple-500/20 text-purple-400",
            hired: "bg-green-500/20 text-green-400",
            rejected: "bg-red-500/20 text-red-400",
        };
        const labels: Record<string, string> = {
            new: "Nuevo",
            reviewed: "Revisado",
            shortlisted: "Preseleccionado",
            interview: "En Entrevista",
            hired: "Contratado",
            rejected: "Rechazado",
        };
        return (
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${styles[status] || "bg-slate-500/20 text-slate-400"}`}>
                {labels[status] || status}
            </span>
        );
    };

    const noteTypeLabels: Record<string, string> = {
        general: "Nota General",
        interview: "Entrevista",
        feedback: "Feedback",
        status_change: "Cambio de Estado",
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
                <p className="text-slate-400">Cargando perfil del candidato...</p>
            </div>
        );
    }

    if (error || !candidate) {
        return (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
                <span className="material-symbols-outlined text-[64px] text-red-400">error</span>
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Error</h2>
                <p className="text-slate-500">{error || "Candidato no encontrado"}</p>
                <Link
                    href="/candidates"
                    className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600"
                >
                    <span className="material-symbols-outlined text-[20px]">arrow_back</span>
                    Volver a Candidatos
                </Link>
            </div>
        );
    }

    const initials = candidate.full_name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();

    return (
        <>
            {/* Back Button */}
            <div className="mb-6">
                <button
                    onClick={() => router.back()}
                    className="flex items-center gap-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
                >
                    <span className="material-symbols-outlined text-[20px]">arrow_back</span>
                    Volver
                </button>
            </div>

            {/* Header Card */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 mb-6 shadow-sm">
                <div className="flex flex-col md:flex-row gap-6">
                    {/* Avatar */}
                    <div className="flex-shrink-0">
                        <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center">
                            <span className="text-3xl font-bold text-white">{initials}</span>
                        </div>
                    </div>

                    {/* Info */}
                    <div className="flex-1">
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
                                    {candidate.full_name}
                                </h1>
                                {candidate.email && (
                                    <p className="text-slate-500 flex items-center gap-2">
                                        <span className="material-symbols-outlined text-[18px]">mail</span>
                                        {candidate.email}
                                    </p>
                                )}
                                {candidate.phone && (
                                    <p className="text-slate-500 flex items-center gap-2 mt-1">
                                        <span className="material-symbols-outlined text-[18px]">phone</span>
                                        {candidate.phone}
                                    </p>
                                )}
                                {candidate.linkedin && (
                                    <a
                                        href={candidate.linkedin.startsWith('http') ? candidate.linkedin : `https://${candidate.linkedin}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-primary flex items-center gap-2 mt-1 hover:underline"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">link</span>
                                        LinkedIn
                                    </a>
                                )}

                                {/* Star Rating */}
                                <div className="flex items-center gap-1 mt-2">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                        <button
                                            key={star}
                                            onClick={() => handleRatingChange(star)}
                                            onMouseEnter={() => setHoverRating(star)}
                                            onMouseLeave={() => setHoverRating(0)}
                                            className="p-0.5"
                                        >
                                            <span
                                                className={`material-symbols-outlined text-[24px] transition-colors ${star <= (hoverRating || rating)
                                                    ? "text-amber-400"
                                                    : "text-slate-300 dark:text-slate-600"
                                                    }`}
                                            >
                                                {star <= (hoverRating || rating) ? "star" : "star"}
                                            </span>
                                        </button>
                                    ))}
                                    <span className="text-sm text-slate-500 ml-2">
                                        {rating > 0 ? `${rating}/5` : "Sin calificar"}
                                    </span>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                {getStatusBadge(candidate.status)}
                                <button
                                    onClick={() => setShowStatusModal(true)}
                                    className="p-2 text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                                    title="Cambiar estado"
                                >
                                    <span className="material-symbols-outlined text-[20px]">edit</span>
                                </button>
                            </div>
                        </div>

                        {/* Quick Stats + CV Buttons */}
                        <div className="flex flex-wrap items-center gap-6 mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
                            <div>
                                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Experiencia</p>
                                <p className="text-lg font-bold text-slate-900 dark:text-white">
                                    {candidate.total_experience_years} años
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Habilidades</p>
                                <p className="text-lg font-bold text-slate-900 dark:text-white">
                                    {candidate.skills?.length || 0}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Posiciones</p>
                                <p className="text-lg font-bold text-slate-900 dark:text-white">
                                    {candidate.experience?.length || 0}
                                </p>
                            </div>
                            <div className="ml-auto flex gap-2">
                                <button
                                    onClick={() => handleOpenFile("preview")}
                                    disabled={loadingFile !== null}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 font-medium text-sm transition-colors disabled:opacity-50"
                                >
                                    <span className="material-symbols-outlined text-[18px]">
                                        {loadingFile === "preview" ? "sync" : "visibility"}
                                    </span>
                                    {loadingFile === "preview" ? "Cargando..." : "Ver CV"}
                                </button>
                                <button
                                    onClick={() => handleOpenFile("download")}
                                    disabled={loadingFile !== null}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 font-medium text-sm transition-colors disabled:opacity-50"
                                >
                                    <span className="material-symbols-outlined text-[18px]">
                                        {loadingFile === "download" ? "sync" : "download"}
                                    </span>
                                    {loadingFile === "download" ? "Descargando..." : "Descargar"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column - Skills & Actions */}
                <div className="lg:col-span-1 space-y-6">
                    {/* Skills Card */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary">psychology</span>
                            Habilidades
                        </h3>
                        <div className="flex flex-wrap gap-2">
                            {candidate.skills?.length > 0 ? (
                                candidate.skills.map((skill, i) => (
                                    <span
                                        key={i}
                                        className="px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-sm font-medium"
                                    >
                                        {skill}
                                    </span>
                                ))
                            ) : (
                                <p className="text-slate-500 text-sm">No se detectaron habilidades</p>
                            )}
                        </div>
                    </div>

                    {/* Quick Status Actions */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Acciones Rápidas</h3>
                        <div className="space-y-2">
                            <button
                                onClick={() => { setSelectedStatus("shortlisted"); setShowStatusModal(true); }}
                                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-emerald-500 text-white font-medium hover:bg-emerald-600 transition-colors"
                            >
                                <span className="material-symbols-outlined">thumb_up</span>
                                Preseleccionar
                            </button>
                            <button
                                onClick={() => { setSelectedStatus("interview"); setShowStatusModal(true); }}
                                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-purple-500 text-white font-medium hover:bg-purple-600 transition-colors"
                            >
                                <span className="material-symbols-outlined">calendar_month</span>
                                Programar Entrevista
                            </button>
                            <button
                                onClick={() => { setSelectedStatus("rejected"); setShowStatusModal(true); }}
                                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-red-300 dark:border-red-700 text-red-500 font-medium hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                            >
                                <span className="material-symbols-outlined">thumb_down</span>
                                Rechazar
                            </button>

                            {/* Delete Button */}
                            <button
                                onClick={() => setShowDeleteModal(true)}
                                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-500 font-medium hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-500 hover:border-red-300 transition-colors"
                            >
                                <span className="material-symbols-outlined">delete</span>
                                Eliminar Candidato
                            </button>
                        </div>
                    </div>

                    {/* Add Note Card */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                            <span className="material-symbols-outlined text-blue-500">edit_note</span>
                            Agregar Nota
                        </h3>
                        <div className="space-y-3">
                            <select
                                value={noteType}
                                onChange={(e) => setNoteType(e.target.value)}
                                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
                            >
                                <option value="general">Nota General</option>
                                <option value="interview">Entrevista</option>
                                <option value="feedback">Feedback</option>
                            </select>
                            <textarea
                                value={newNote}
                                onChange={(e) => setNewNote(e.target.value)}
                                placeholder="Escribe una nota..."
                                rows={3}
                                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm resize-none"
                            />
                            <button
                                onClick={handleAddNote}
                                disabled={!newNote.trim() || submittingNote}
                                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                {submittingNote ? (
                                    <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                                ) : (
                                    <span className="material-symbols-outlined text-[18px]">add</span>
                                )}
                                Guardar Nota
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right Column */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Notes Timeline */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                            <span className="material-symbols-outlined text-blue-500">history</span>
                            Historial de Notas
                            <span className="text-sm font-normal text-slate-400 ml-2">({notes.length})</span>
                        </h3>
                        {notes.length > 0 ? (
                            <div className="space-y-4">
                                {notes.map((note) => (
                                    <div
                                        key={note.id}
                                        className={`p-4 rounded-lg border-l-4 ${note.note_type === "status_change"
                                            ? "border-l-amber-500 bg-amber-50/50 dark:bg-amber-900/10"
                                            : note.note_type === "interview"
                                                ? "border-l-purple-500 bg-purple-50/50 dark:bg-purple-900/10"
                                                : "border-l-blue-500 bg-blue-50/50 dark:bg-blue-900/10"
                                            }`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div>
                                                <span className="text-xs font-medium text-slate-500 uppercase">
                                                    {noteTypeLabels[note.note_type] || note.note_type}
                                                </span>
                                                {note.previous_status && note.new_status && (
                                                    <span className="text-xs text-slate-400 ml-2">
                                                        {note.previous_status} → {note.new_status}
                                                    </span>
                                                )}
                                            </div>
                                            <span className="text-xs text-slate-400">
                                                {new Date(note.created_at).toLocaleDateString("es-ES", {
                                                    day: "2-digit",
                                                    month: "short",
                                                    year: "numeric",
                                                    hour: "2-digit",
                                                    minute: "2-digit"
                                                })}
                                            </span>
                                        </div>
                                        <p className="text-slate-700 dark:text-slate-300 mt-2">
                                            {note.content}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-slate-500">
                                <span className="material-symbols-outlined text-[32px] block mb-2">notes</span>
                                <p className="text-sm">No hay notas aún</p>
                            </div>
                        )}
                    </div>

                    {/* Experience Card */}

                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                            <span className="material-symbols-outlined text-emerald-500">work</span>
                            Experiencia Laboral
                        </h3>
                        {candidate.experience?.length > 0 ? (
                            <div className="relative pl-6 border-l-2 border-slate-200 dark:border-slate-700 space-y-6">
                                {candidate.experience.map((exp, i) => {
                                    // Extract periodo from description (format: "Periodo: Enero 2021 - Mayo 2024\nLogro1\nLogro2")
                                    const descLines = (exp.description || "").split("\n");
                                    const periodoLine = descLines.find((l: string) => l.startsWith("Periodo:"));
                                    const periodoRaw = periodoLine ? periodoLine.replace("Periodo: ", "").trim() : null;
                                    // Treat "null", empty, or single dash as no period
                                    const periodo = (periodoRaw && periodoRaw !== "null" && periodoRaw !== "-" && periodoRaw !== " - ") ? periodoRaw : null;
                                    const logros = descLines.filter((l: string) => !l.startsWith("Periodo:") && l.trim());

                                    // Format ISO date "2021-12-01" → "Dic 2021"
                                    const formatDate = (d: string | null | undefined): string => {
                                        if (!d || d === "null") return "";
                                        const match = d.match(/^(\d{4})-(\d{2})/);
                                        if (!match) return d;
                                        const months = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
                                        return `${months[parseInt(match[2], 10) - 1]} ${match[1]}`;
                                    };

                                    // Determine date display
                                    let dateDisplay = periodo;
                                    if (!dateDisplay) {
                                        const start = exp.start_date ? formatDate(exp.start_date) : null;
                                        const end = exp.is_current ? "Presente" : (exp.end_date ? formatDate(exp.end_date) : "Presente");
                                        dateDisplay = start ? `${start} - ${end}` : end;
                                    }

                                    return (
                                        <div key={i} className="relative">
                                            <div className={`absolute -left-[29px] w-4 h-4 rounded-full border-4 border-white dark:border-slate-800 ${
                                                exp.is_current ? "bg-emerald-500" : "bg-blue-500"
                                            }`}></div>
                                            <div>
                                                <h4 className="font-bold text-slate-900 dark:text-white">{exp.title}</h4>
                                                <p className="text-primary font-medium">{exp.company}</p>
                                                <p className="text-sm text-slate-500 mt-1 flex items-center gap-1">
                                                    <span className="material-symbols-outlined text-[16px]">calendar_today</span>
                                                    {dateDisplay}
                                                    {exp.is_current && (
                                                        <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-emerald-500/20 text-emerald-400">Actual</span>
                                                    )}
                                                </p>
                                                {logros.length > 0 && (
                                                    <ul className="mt-2 space-y-1">
                                                        {logros.map((logro: string, li: number) => (
                                                            <li key={li} className="text-slate-600 dark:text-slate-400 text-sm flex items-start gap-2">
                                                                <span className="text-emerald-500 mt-0.5">•</span>
                                                                {logro}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-slate-500">
                                <span className="material-symbols-outlined text-[32px] block mb-2">work_off</span>
                                <p className="text-sm">No se detectó experiencia laboral</p>
                            </div>
                        )}
                    </div>

                    {/* Education - Two Groups */}
                    {(() => {
                        const educacion = (candidate.education || []).filter((e: any) => (e.education_type || 'educacion') === 'educacion');
                        const certificaciones = (candidate.education || []).filter((e: any) => (e.education_type) === 'certificacion');
                        
                        return (
                            <>
                                {/* Formación Académica */}
                                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                                        <span className="material-symbols-outlined text-amber-500">school</span>
                                        Formación Académica
                                    </h3>
                                    {educacion.length > 0 ? (
                                        <div className="space-y-4">
                                            {educacion.map((edu: any, i: number) => (
                                                <div key={i} className="flex items-start gap-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                                                    <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                                                        <span className="material-symbols-outlined text-amber-500">school</span>
                                                    </div>
                                                    <div>
                                                        <h4 className="font-bold text-slate-900 dark:text-white">{edu.degree}</h4>
                                                        <p className="text-slate-600 dark:text-slate-400">{edu.institution}</p>
                                                        {edu.field_of_study && (
                                                            <p className="text-sm text-slate-500">{edu.field_of_study}</p>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-center py-6 text-slate-500">
                                            <span className="material-symbols-outlined text-[28px] block mb-2">school</span>
                                            <p className="text-sm">No se detectó formación académica</p>
                                        </div>
                                    )}
                                </div>

                                {/* Certificaciones */}
                                {certificaciones.length > 0 && (
                                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                                            <span className="material-symbols-outlined text-purple-500">workspace_premium</span>
                                            Certificaciones
                                        </h3>
                                        <div className="space-y-3">
                                            {certificaciones.map((cert: any, i: number) => (
                                                <div key={i} className="flex items-start gap-4 p-3 rounded-lg bg-purple-50/50 dark:bg-purple-900/10 border border-purple-200/50 dark:border-purple-800/30">
                                                    <div className="w-9 h-9 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                                                        <span className="material-symbols-outlined text-purple-500 text-[20px]">verified</span>
                                                    </div>
                                                    <div>
                                                        <h4 className="font-medium text-slate-900 dark:text-white">{cert.degree}</h4>
                                                        <p className="text-sm text-slate-500">{cert.institution}</p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </>
                        );
                    })()}
                </div>
            </div>

            {/* Status Change Modal */}
            {showStatusModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-md shadow-xl">
                        <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-4">
                            Cambiar Estado
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm font-medium text-slate-500 block mb-2">Nuevo Estado</label>
                                <select
                                    value={selectedStatus}
                                    onChange={(e) => setSelectedStatus(e.target.value)}
                                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg"
                                >
                                    <option value="">Seleccionar...</option>
                                    <option value="new">Nuevo</option>
                                    <option value="reviewed">Revisado</option>
                                    <option value="shortlisted">Preseleccionado</option>
                                    <option value="interview">En Entrevista</option>
                                    <option value="hired">Contratado</option>
                                    <option value="rejected">Rechazado</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-sm font-medium text-slate-500 block mb-2">Motivo (opcional)</label>
                                <textarea
                                    value={statusReason}
                                    onChange={(e) => setStatusReason(e.target.value)}
                                    placeholder="Explica por qué cambias el estado..."
                                    rows={3}
                                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg resize-none"
                                />
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button
                                    onClick={() => { setShowStatusModal(false); setStatusReason(""); }}
                                    className="flex-1 py-2 px-4 rounded-lg border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-medium hover:bg-slate-50 dark:hover:bg-slate-700"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleStatusChange}
                                    disabled={!selectedStatus}
                                    className="flex-1 py-2 px-4 rounded-lg bg-primary text-white font-medium hover:bg-blue-600 disabled:opacity-50"
                                >
                                    Guardar
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {showDeleteModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-md shadow-xl">
                        <div className="text-center mb-6">
                            <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 mx-auto mb-4 flex items-center justify-center">
                                <span className="material-symbols-outlined text-red-500 text-[32px]">warning</span>
                            </div>
                            <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">
                                ¿Eliminar Candidato?
                            </h3>
                            <p className="text-slate-500">
                                Esta acción eliminará permanentemente a <strong>{candidate.full_name}</strong> y toda su información. No se puede deshacer.
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowDeleteModal(false)}
                                disabled={deleting}
                                className="flex-1 py-2 px-4 rounded-lg border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-medium hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleDelete}
                                disabled={deleting}
                                className="flex-1 py-2 px-4 rounded-lg bg-red-500 text-white font-medium hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {deleting ? (
                                    <>
                                        <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                                        Eliminando...
                                    </>
                                ) : (
                                    <>
                                        <span className="material-symbols-outlined text-[18px]">delete</span>
                                        Sí, Eliminar
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default CandidateDetailPage;
