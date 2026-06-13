"use client";

import { useEffect, useState } from "react";
import { authApi, AppUser, UserRole } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

type Feedback = { type: "success" | "error"; text: string } | null;

const ROLE_LABEL: Record<UserRole, string> = {
    admin: "Administrador",
    recruiter: "Reclutador",
};

const ROLE_BADGE: Record<UserRole, string> = {
    admin: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    recruiter: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
};

const UsersSection: React.FC = () => {
    const { user: currentUser } = useAuth();

    const [users, setUsers] = useState<AppUser[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [feedback, setFeedback] = useState<Feedback>(null);

    // Change-my-password form state
    const [myCurrentPwd, setMyCurrentPwd] = useState("");
    const [myNewPwd, setMyNewPwd] = useState("");
    const [myNewPwd2, setMyNewPwd2] = useState("");
    const [isChangingMyPwd, setIsChangingMyPwd] = useState(false);

    // Create-user form state
    const [createOpen, setCreateOpen] = useState(false);
    const [newEmail, setNewEmail] = useState("");
    const [newName, setNewName] = useState("");
    const [newPwd, setNewPwd] = useState("");
    const [newRole, setNewRole] = useState<UserRole>("recruiter");
    const [isCreating, setIsCreating] = useState(false);

    // Per-user inline reset-password state
    const [resetTargetId, setResetTargetId] = useState<string | null>(null);
    const [resetPwd, setResetPwd] = useState("");
    const [isResetting, setIsResetting] = useState(false);

    const showOk = (text: string) => {
        setFeedback({ type: "success", text });
        setTimeout(() => setFeedback(null), 3500);
    };
    const showErr = (text: string) => {
        setFeedback({ type: "error", text });
        setTimeout(() => setFeedback(null), 5000);
    };

    const loadUsers = async () => {
        try {
            const res = await authApi.listUsers();
            setUsers(res.data);
        } catch (err: any) {
            showErr(err.response?.data?.detail || "No se pudo cargar la lista de usuarios");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadUsers();
    }, []);

    const handleChangeMyPassword = async (e: React.FormEvent) => {
        e.preventDefault();
        if (myNewPwd.length < 8) {
            showErr("La nueva contraseña debe tener al menos 8 caracteres");
            return;
        }
        if (myNewPwd !== myNewPwd2) {
            showErr("Las contraseñas nuevas no coinciden");
            return;
        }
        setIsChangingMyPwd(true);
        try {
            await authApi.changeMyPassword(myCurrentPwd, myNewPwd);
            showOk("Tu contraseña fue actualizada correctamente");
            setMyCurrentPwd("");
            setMyNewPwd("");
            setMyNewPwd2("");
        } catch (err: any) {
            showErr(err.response?.data?.detail || "No se pudo cambiar la contraseña");
        } finally {
            setIsChangingMyPwd(false);
        }
    };

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        if (newPwd.length < 8) {
            showErr("La contraseña debe tener al menos 8 caracteres");
            return;
        }
        setIsCreating(true);
        try {
            await authApi.createUser(
                { email: newEmail.trim().toLowerCase(), full_name: newName.trim(), password: newPwd },
                newRole,
            );
            showOk(`Usuario ${newEmail} creado correctamente`);
            setNewEmail("");
            setNewName("");
            setNewPwd("");
            setNewRole("recruiter");
            setCreateOpen(false);
            await loadUsers();
        } catch (err: any) {
            showErr(err.response?.data?.detail || "No se pudo crear el usuario");
        } finally {
            setIsCreating(false);
        }
    };

    const handleResetPassword = async (userId: string) => {
        if (resetPwd.length < 8) {
            showErr("La contraseña debe tener al menos 8 caracteres");
            return;
        }
        setIsResetting(true);
        try {
            await authApi.resetUserPassword(userId, resetPwd);
            showOk("Contraseña restablecida");
            setResetTargetId(null);
            setResetPwd("");
        } catch (err: any) {
            showErr(err.response?.data?.detail || "No se pudo restablecer la contraseña");
        } finally {
            setIsResetting(false);
        }
    };

    const handleToggleStatus = async (u: AppUser) => {
        try {
            await authApi.updateUserStatus(u.id, !u.is_active);
            showOk(`Usuario ${u.is_active ? "desactivado" : "activado"}`);
            await loadUsers();
        } catch (err: any) {
            showErr(err.response?.data?.detail || "No se pudo cambiar el estado");
        }
    };

    const handleDelete = async (u: AppUser) => {
        if (!confirm(`¿Eliminar al usuario ${u.email}? Esta acción no se puede deshacer.`)) return;
        try {
            await authApi.deleteUser(u.id);
            showOk(`Usuario ${u.email} eliminado`);
            await loadUsers();
        } catch (err: any) {
            showErr(err.response?.data?.detail || "No se pudo eliminar el usuario");
        }
    };

    if (currentUser?.role !== "admin") return null;

    return (
        <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-rose-500">manage_accounts</span>
                    Usuarios y Contraseñas
                </h2>
                <p className="text-xs text-slate-500 mt-1">
                    Gestión de usuarios del sistema. Solo accesible para administradores.
                </p>
            </div>

            <div className="p-6 space-y-6">
                {/* ── Cambiar mi contraseña ─────────────────────────────────── */}
                <form
                    onSubmit={handleChangeMyPassword}
                    className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700 space-y-3"
                >
                    <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary text-[20px]">key</span>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">
                            Cambiar mi contraseña
                        </h3>
                        {currentUser && (
                            <span className="text-xs text-slate-400 ml-auto">
                                {currentUser.email}
                            </span>
                        )}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <input
                            type="password"
                            placeholder="Contraseña actual"
                            value={myCurrentPwd}
                            onChange={e => setMyCurrentPwd(e.target.value)}
                            required
                            autoComplete="current-password"
                            className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                        />
                        <input
                            type="password"
                            placeholder="Nueva (mín. 8)"
                            value={myNewPwd}
                            onChange={e => setMyNewPwd(e.target.value)}
                            required
                            minLength={8}
                            autoComplete="new-password"
                            className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                        />
                        <input
                            type="password"
                            placeholder="Repetir nueva"
                            value={myNewPwd2}
                            onChange={e => setMyNewPwd2(e.target.value)}
                            required
                            minLength={8}
                            autoComplete="new-password"
                            className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={isChangingMyPwd}
                        className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
                    >
                        {isChangingMyPwd && (
                            <span className="material-symbols-outlined text-[16px] animate-spin">
                                progress_activity
                            </span>
                        )}
                        {isChangingMyPwd ? "Actualizando..." : "Actualizar mi contraseña"}
                    </button>
                </form>

                {/* ── Lista de usuarios ─────────────────────────────────────── */}
                <div>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                            <span className="material-symbols-outlined text-slate-500 text-[20px]">group</span>
                            Usuarios del sistema
                            <span className="text-xs text-slate-400 font-normal">
                                ({users.length})
                            </span>
                        </h3>
                        <button
                            onClick={() => setCreateOpen(v => !v)}
                            className="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-1.5"
                        >
                            <span className="material-symbols-outlined text-[16px]">
                                {createOpen ? "close" : "person_add"}
                            </span>
                            {createOpen ? "Cancelar" : "Nuevo usuario"}
                        </button>
                    </div>

                    {/* Create form */}
                    {createOpen && (
                        <form
                            onSubmit={handleCreateUser}
                            className="p-4 mb-4 rounded-lg bg-primary/5 dark:bg-primary/10 border border-primary/30 space-y-3"
                        >
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <input
                                    type="email"
                                    placeholder="email@empresa.com"
                                    value={newEmail}
                                    onChange={e => setNewEmail(e.target.value)}
                                    required
                                    className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                />
                                <input
                                    type="text"
                                    placeholder="Nombre completo"
                                    value={newName}
                                    onChange={e => setNewName(e.target.value)}
                                    required
                                    minLength={2}
                                    className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                />
                                <input
                                    type="password"
                                    placeholder="Contraseña inicial (mín. 8)"
                                    value={newPwd}
                                    onChange={e => setNewPwd(e.target.value)}
                                    required
                                    minLength={8}
                                    autoComplete="new-password"
                                    className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                />
                                <select
                                    value={newRole}
                                    onChange={e => setNewRole(e.target.value as UserRole)}
                                    className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                >
                                    <option value="recruiter">Reclutador</option>
                                    <option value="admin">Administrador</option>
                                </select>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    type="submit"
                                    disabled={isCreating}
                                    className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
                                >
                                    {isCreating && (
                                        <span className="material-symbols-outlined text-[16px] animate-spin">
                                            progress_activity
                                        </span>
                                    )}
                                    {isCreating ? "Creando..." : "Crear usuario"}
                                </button>
                                <p className="text-xs text-slate-400">
                                    El usuario podrá cambiar su contraseña tras iniciar sesión.
                                </p>
                            </div>
                        </form>
                    )}

                    {/* Users list */}
                    {isLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <span className="material-symbols-outlined animate-spin text-primary text-[24px]">
                                progress_activity
                            </span>
                        </div>
                    ) : users.length === 0 ? (
                        <p className="text-sm text-slate-400 text-center py-6">No hay usuarios registrados</p>
                    ) : (
                        <ul className="space-y-2">
                            {users.map(u => {
                                const isMe = u.id === currentUser?.id;
                                const role = (u.role as UserRole) || "recruiter";
                                return (
                                    <li
                                        key={u.id}
                                        className="p-3 rounded-lg bg-white dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700"
                                    >
                                        <div className="flex items-center gap-3 flex-wrap">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                                                        {u.full_name}
                                                    </span>
                                                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${ROLE_BADGE[role]}`}>
                                                        {ROLE_LABEL[role]}
                                                    </span>
                                                    {!u.is_active && (
                                                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400 font-medium">
                                                            inactivo
                                                        </span>
                                                    )}
                                                    {isMe && (
                                                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/20 text-primary font-medium">
                                                            tú
                                                        </span>
                                                    )}
                                                </div>
                                                <span className="text-xs text-slate-500 truncate block">{u.email}</span>
                                            </div>

                                            <div className="flex items-center gap-1.5">
                                                <button
                                                    onClick={() =>
                                                        setResetTargetId(resetTargetId === u.id ? null : u.id)
                                                    }
                                                    className="px-2 py-1 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded flex items-center gap-1"
                                                    title="Resetear contraseña"
                                                >
                                                    <span className="material-symbols-outlined text-[16px]">key</span>
                                                    Resetear
                                                </button>
                                                {!isMe && (
                                                    <>
                                                        <button
                                                            onClick={() => handleToggleStatus(u)}
                                                            className="px-2 py-1 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded flex items-center gap-1"
                                                            title={u.is_active ? "Desactivar" : "Activar"}
                                                        >
                                                            <span className="material-symbols-outlined text-[16px]">
                                                                {u.is_active ? "person_off" : "person_check"}
                                                            </span>
                                                            {u.is_active ? "Desactivar" : "Activar"}
                                                        </button>
                                                        <button
                                                            onClick={() => handleDelete(u)}
                                                            className="px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/20 rounded flex items-center gap-1"
                                                            title="Eliminar usuario"
                                                        >
                                                            <span className="material-symbols-outlined text-[16px]">
                                                                delete
                                                            </span>
                                                            Eliminar
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </div>

                                        {/* Inline reset-password form */}
                                        {resetTargetId === u.id && (
                                            <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700 flex items-center gap-2">
                                                <input
                                                    type="password"
                                                    placeholder="Nueva contraseña (mín. 8)"
                                                    value={resetPwd}
                                                    onChange={e => setResetPwd(e.target.value)}
                                                    minLength={8}
                                                    autoComplete="new-password"
                                                    className="flex-1 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                                />
                                                <button
                                                    onClick={() => handleResetPassword(u.id)}
                                                    disabled={isResetting}
                                                    className="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
                                                >
                                                    {isResetting && (
                                                        <span className="material-symbols-outlined text-[14px] animate-spin">
                                                            progress_activity
                                                        </span>
                                                    )}
                                                    Confirmar
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setResetTargetId(null);
                                                        setResetPwd("");
                                                    }}
                                                    className="px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded"
                                                >
                                                    Cancelar
                                                </button>
                                            </div>
                                        )}
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>

                {/* Feedback */}
                {feedback && (
                    <div
                        className={`p-3 rounded-lg flex items-center gap-2 text-sm ${
                            feedback.type === "success"
                                ? "bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300"
                                : "bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300"
                        }`}
                    >
                        <span className="material-symbols-outlined text-[16px]">
                            {feedback.type === "success" ? "check_circle" : "error"}
                        </span>
                        {feedback.text}
                    </div>
                )}

                <p className="text-xs text-slate-400 flex items-start gap-1">
                    <span className="material-symbols-outlined text-[14px] mt-0.5">lock</span>
                    Todas las contraseñas se almacenan con bcrypt. Los administradores pueden resetear
                    contraseñas pero nunca verlas.
                </p>
            </div>
        </div>
    );
};

export default UsersSection;
