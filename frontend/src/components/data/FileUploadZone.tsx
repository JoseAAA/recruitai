"use client";

import { useState, useCallback, useRef } from "react";

interface FileUploadZoneProps {
    onFilesSelected: (files: File[]) => void;
    isUploading: boolean;
    uploadProgress: number;
    currentFile?: string;
    completedCount?: number;
    totalFiles?: number;
    estimatedRemaining?: string;
}

const FileUploadZone: React.FC<FileUploadZoneProps> = ({
    onFilesSelected,
    isUploading,
    uploadProgress,
    currentFile,
    completedCount,
    totalFiles,
    estimatedRemaining,
}) => {
    const [isDragOver, setIsDragOver] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const acceptedTypes = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/rtf",
    ];

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);

            const files = Array.from(e.dataTransfer.files).filter((file) =>
                acceptedTypes.some(
                    (type) => file.type === type || file.name.endsWith(".pdf") || file.name.endsWith(".docx")
                )
            );

            if (files.length > 0) {
                setSelectedFiles(files);
                onFilesSelected(files);
            }
        },
        [onFilesSelected]
    );

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length > 0) {
            setSelectedFiles(files);
            onFilesSelected(files);
        }
    };

    const handleClick = () => {
        fileInputRef.current?.click();
    };

    const removeFile = (index: number) => {
        const newFiles = selectedFiles.filter((_, i) => i !== index);
        setSelectedFiles(newFiles);
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    };

    return (
        <div className="space-y-4">
            {/* Drop Zone */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={handleClick}
                className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${isDragOver
                        ? "border-primary bg-primary/10"
                        : "border-slate-300 dark:border-slate-600 hover:border-slate-400 dark:hover:border-slate-500 bg-slate-50 dark:bg-slate-800/30 hover:bg-slate-100 dark:hover:bg-slate-800/50"
                    }`}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt,.rtf"
                    onChange={handleFileSelect}
                    className="hidden"
                />

                <div className="flex flex-col items-center gap-4">
                    <div
                        className={`p-4 rounded-full ${isDragOver ? "bg-primary/20" : "bg-slate-200 dark:bg-slate-700"
                            }`}
                    >
                        <span
                            className={`material-symbols-outlined text-[48px] ${isDragOver ? "text-primary" : "text-slate-400"
                                }`}
                        >
                            cloud_upload
                        </span>
                    </div>
                    <div>
                        <p className="text-lg font-semibold text-slate-900 dark:text-white">
                            {isDragOver
                                ? "Suelta los archivos aquí"
                                : "Arrastra tus CVs aquí"}
                        </p>
                        <p className="text-sm text-slate-400 mt-1">
                            o haz clic para seleccionar archivos
                        </p>
                    </div>
                    <div className="flex flex-wrap justify-center gap-2 mt-2">
                        {["PDF", "DOCX", "DOC", "TXT"].map((format) => (
                            <span
                                key={format}
                                className="px-2 py-0.5 bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded text-xs"
                            >
                                .{format.toLowerCase()}
                            </span>
                        ))}
                    </div>
                </div>
            </div>

            {/* Selected Files List */}
            {selectedFiles.length > 0 && (
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                            {selectedFiles.length} archivo(s) seleccionado(s)
                        </p>
                        <button
                            onClick={() => setSelectedFiles([])}
                            className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                        >
                            Limpiar todo
                        </button>
                    </div>

                    <div className="max-h-48 overflow-y-auto space-y-2 pr-2">
                        {selectedFiles.map((file, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    <span className="material-symbols-outlined text-slate-400 text-[20px]">
                                        description
                                    </span>
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                                            {file.name}
                                        </p>
                                        <p className="text-xs text-slate-500">
                                            {formatFileSize(file.size)}
                                        </p>
                                    </div>
                                </div>
                                {!isUploading && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            removeFile(index);
                                        }}
                                        className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">
                                            close
                                        </span>
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Upload Progress */}
            {isUploading && (
                <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 space-y-3">
                    {/* Header: count + % */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-[20px] animate-spin">
                                sync
                            </span>
                            <span className="text-sm font-medium text-slate-900 dark:text-white">
                                {completedCount != null && totalFiles
                                    ? `${completedCount} de ${totalFiles} CVs procesados`
                                    : "Procesando CVs..."}
                            </span>
                        </div>
                        <span className="text-sm font-bold text-primary">{uploadProgress}%</span>
                    </div>

                    {/* Progress bar */}
                    <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary transition-all duration-300"
                            style={{ width: `${uploadProgress}%` }}
                        />
                    </div>

                    {/* Footer: current file + time remaining */}
                    <div className="flex items-center justify-between gap-2">
                        <p className="text-xs text-slate-500 truncate">
                            {currentFile
                                ? <><span className="text-slate-400">Procesando:</span> {currentFile}</>
                                : "Extrayendo información con IA..."}
                        </p>
                        {estimatedRemaining && (
                            <span className="text-xs text-amber-400 flex-shrink-0 flex items-center gap-1">
                                <span className="material-symbols-outlined text-[14px]">schedule</span>
                                {estimatedRemaining} restantes
                            </span>
                        )}
                    </div>

                    {/* Note for large batches */}
                    {totalFiles != null && totalFiles > 10 && (
                        <p className="text-xs text-slate-500 dark:text-slate-600 border-t border-slate-200 dark:border-slate-700 pt-2">
                            Lote grande — puedes dejar esta página abierta y volver cuando termine.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

export default FileUploadZone;
