"use client";

import { useState } from "react";

interface ConnectionModalProps {
    isOpen: boolean;
    onClose: () => void;
    sourceType: "google_drive" | "onedrive" | "manual";
    sourceName: string;
}

const ConnectionModal: React.FC<ConnectionModalProps> = ({
    isOpen,
    onClose,
    sourceType,
    sourceName,
}) => {
    const [folderPath, setFolderPath] = useState("");
    const [autoSync, setAutoSync] = useState(true);
    const [syncInterval, setSyncInterval] = useState("30");
    const [isConnecting, setIsConnecting] = useState(false);

    if (!isOpen) return null;

    const handleConnect = async () => {
        setIsConnecting(true);
        // Simulate connection
        await new Promise((resolve) => setTimeout(resolve, 2000));
        setIsConnecting(false);
        onClose();
    };

    const handleDisconnect = () => {
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-lg mx-4 shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-slate-700">
                    <div className="flex items-center gap-3">
                        <div
                            className={`p-2 rounded-lg ${sourceType === "google_drive"
                                    ? "bg-blue-500/20 text-blue-400"
                                    : sourceType === "onedrive"
                                        ? "bg-cyan-500/20 text-cyan-400"
                                        : "bg-slate-500/20 text-slate-400"
                                }`}
                        >
                            <span className="material-symbols-outlined text-[24px]">
                                {sourceType === "google_drive"
                                    ? "cloud"
                                    : sourceType === "onedrive"
                                        ? "cloud_sync"
                                        : "folder_open"}
                            </span>
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-white">
                                Configurar {sourceName}
                            </h2>
                            <p className="text-sm text-slate-400">
                                Gestiona la conexión y sincronización
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                    >
                        <span className="material-symbols-outlined">close</span>
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-5">
                    {sourceType !== "manual" ? (
                        <>
                            {/* OAuth Connection */}
                            <div className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-medium text-white">Estado de Conexión</p>
                                        <p className="text-sm text-slate-400">
                                            {sourceType === "google_drive"
                                                ? "Conectado como usuario@gmail.com"
                                                : "Conectado como usuario@outlook.com"}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                                        <span className="text-sm font-medium text-emerald-400">
                                            Conectado
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Folder Path */}
                            <div className="space-y-2">
                                <label className="block text-sm font-medium text-slate-300">
                                    Carpeta de Sincronización
                                </label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={folderPath}
                                        onChange={(e) => setFolderPath(e.target.value)}
                                        placeholder={
                                            sourceType === "google_drive"
                                                ? "/Mi unidad/RRHH/CVs"
                                                : "/OneDrive/RRHH/CVs"
                                        }
                                        className="flex-1 px-4 py-2.5 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                                    />
                                    <button className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition-colors">
                                        <span className="material-symbols-outlined text-[20px]">
                                            folder_open
                                        </span>
                                    </button>
                                </div>
                            </div>

                            {/* Auto Sync */}
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-medium text-white">
                                        Sincronización Automática
                                    </p>
                                    <p className="text-sm text-slate-400">
                                        Detectar nuevos archivos automáticamente
                                    </p>
                                </div>
                                <button
                                    onClick={() => setAutoSync(!autoSync)}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${autoSync ? "bg-primary" : "bg-slate-600"
                                        }`}
                                >
                                    <span
                                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoSync ? "translate-x-6" : "translate-x-1"
                                            }`}
                                    />
                                </button>
                            </div>

                            {/* Sync Interval */}
                            {autoSync && (
                                <div className="space-y-2">
                                    <label className="block text-sm font-medium text-slate-300">
                                        Intervalo de Sincronización
                                    </label>
                                    <select
                                        value={syncInterval}
                                        onChange={(e) => setSyncInterval(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                                    >
                                        <option value="5">Cada 5 minutos</option>
                                        <option value="15">Cada 15 minutos</option>
                                        <option value="30">Cada 30 minutos</option>
                                        <option value="60">Cada hora</option>
                                    </select>
                                </div>
                            )}
                        </>
                    ) : (
                        <>
                            {/* Manual Upload Info */}
                            <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-xl p-4">
                                <div className="flex items-start gap-3">
                                    <span className="material-symbols-outlined text-indigo-400">
                                        info
                                    </span>
                                    <div>
                                        <p className="font-medium text-indigo-300">
                                            Subida Manual de CVs
                                        </p>
                                        <p className="text-sm text-slate-300 mt-1">
                                            Arrastra archivos PDF o DOCX directamente a la zona de
                                            carga, o haz clic para seleccionar archivos. Puedes subir
                                            múltiples archivos a la vez.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Supported Formats */}
                            <div className="space-y-2">
                                <p className="text-sm font-medium text-slate-300">
                                    Formatos Soportados
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {["PDF", "DOCX", "DOC", "RTF", "TXT"].map((format) => (
                                        <span
                                            key={format}
                                            className="px-3 py-1 bg-slate-700 text-slate-300 rounded-full text-xs font-medium"
                                        >
                                            .{format.toLowerCase()}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {/* Max File Size */}
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-400">Tamaño máximo por archivo</span>
                                <span className="text-white font-medium">10 MB</span>
                            </div>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-6 border-t border-slate-700 bg-slate-800/50 rounded-b-2xl">
                    {sourceType !== "manual" ? (
                        <>
                            <button
                                onClick={handleDisconnect}
                                className="px-4 py-2 text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors text-sm font-medium"
                            >
                                Desconectar Cuenta
                            </button>
                            <div className="flex gap-3">
                                <button
                                    onClick={onClose}
                                    className="px-4 py-2 text-slate-400 hover:text-white transition-colors text-sm font-medium"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleConnect}
                                    disabled={isConnecting}
                                    className="px-5 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                                >
                                    {isConnecting ? (
                                        <>
                                            <span className="material-symbols-outlined text-[18px] animate-spin">
                                                sync
                                            </span>
                                            Guardando...
                                        </>
                                    ) : (
                                        "Guardar Cambios"
                                    )}
                                </button>
                            </div>
                        </>
                    ) : (
                        <div className="flex justify-end w-full">
                            <button
                                onClick={onClose}
                                className="px-5 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors text-sm font-medium"
                            >
                                Entendido
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ConnectionModal;
