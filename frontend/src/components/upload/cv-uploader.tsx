"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { cn } from "@/lib/utils";

interface FileUploadState {
    file: File;
    status: "pending" | "uploading" | "success" | "error";
    progress: number;
    result?: {
        id: string;
        extractedName: string;
        skillsCount: number;
    };
    error?: string;
}

interface CVUploaderProps {
    onUploadComplete?: (results: FileUploadState[]) => void;
}

export function CVUploader({ onUploadComplete }: CVUploaderProps) {
    const [files, setFiles] = useState<FileUploadState[]>([]);
    const [isUploading, setIsUploading] = useState(false);

    const onDrop = useCallback((acceptedFiles: File[]) => {
        const newFiles = acceptedFiles.map((file) => ({
            file,
            status: "pending" as const,
            progress: 0,
        }));
        setFiles((prev) => [...prev, ...newFiles]);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "application/pdf": [".pdf"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
            "application/msword": [".doc"],
        },
        multiple: true,
    });

    const removeFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const uploadFiles = async () => {
        setIsUploading(true);
        const updatedFiles = [...files];

        for (let i = 0; i < updatedFiles.length; i++) {
            if (updatedFiles[i].status !== "pending") continue;

            updatedFiles[i].status = "uploading";
            setFiles([...updatedFiles]);

            for (let progress = 0; progress <= 100; progress += 20) {
                await new Promise((r) => setTimeout(r, 200));
                updatedFiles[i].progress = progress;
                setFiles([...updatedFiles]);
            }

            try {
                await new Promise((r) => setTimeout(r, 500));
                updatedFiles[i].status = "success";
                updatedFiles[i].result = {
                    id: `cand-${Math.random().toString(36).substr(2, 9)}`,
                    extractedName: "John Doe",
                    skillsCount: Math.floor(Math.random() * 10) + 5,
                };
            } catch (err) {
                updatedFiles[i].status = "error";
                updatedFiles[i].error = "Error al procesar archivo";
            }

            setFiles([...updatedFiles]);
        }

        setIsUploading(false);
        onUploadComplete?.(updatedFiles);
    };

    const getStatusIcon = (status: FileUploadState["status"]) => {
        switch (status) {
            case "uploading":
                return <span className="material-symbols-outlined text-[#135bec] animate-spin">progress_activity</span>;
            case "success":
                return <span className="material-symbols-outlined text-emerald-400">check_circle</span>;
            case "error":
                return <span className="material-symbols-outlined text-rose-400">error</span>;
            default:
                return <span className="material-symbols-outlined text-slate-400">description</span>;
        }
    };

    return (
        <div className="space-y-4">
            {/* Dropzone */}
            <div
                {...getRootProps()}
                className={cn(
                    "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all",
                    isDragActive
                        ? "border-[#135bec] bg-[#135bec]/5"
                        : "border-[#334155] hover:border-[#135bec]/50 hover:bg-slate-800/50"
                )}
            >
                <input {...getInputProps()} />
                <span className="material-symbols-outlined text-[48px] text-slate-400 mb-4">cloud_upload</span>
                <p className="text-lg font-medium text-white mb-2">
                    {isDragActive ? "Suelta los archivos aquí..." : "Arrastra y suelta CVs aquí"}
                </p>
                <p className="text-sm text-slate-400">
                    o haz clic para buscar. Soporta archivos PDF y DOCX.
                </p>
            </div>

            {/* File List */}
            {files.length > 0 && (
                <div className="space-y-2">
                    <h4 className="font-medium text-sm text-slate-400">
                        {files.length} archivo(s) seleccionado(s)
                    </h4>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                        {files.map((fileState, index) => (
                            <div
                                key={index}
                                className="flex items-center gap-3 p-3 rounded-lg bg-[#1e293b] border border-[#334155]"
                            >
                                {getStatusIcon(fileState.status)}
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-white truncate">{fileState.file.name}</p>
                                    {fileState.status === "uploading" && (
                                        <div className="h-1 bg-slate-700 rounded-full mt-1 overflow-hidden">
                                            <div
                                                className="h-full bg-[#135bec] transition-all"
                                                style={{ width: `${fileState.progress}%` }}
                                            />
                                        </div>
                                    )}
                                    {fileState.status === "success" && fileState.result && (
                                        <p className="text-xs text-slate-400">
                                            Extraído: {fileState.result.extractedName} • {fileState.result.skillsCount} habilidades
                                        </p>
                                    )}
                                    {fileState.status === "error" && (
                                        <p className="text-xs text-rose-400">{fileState.error}</p>
                                    )}
                                </div>
                                {fileState.status === "pending" && (
                                    <button
                                        onClick={() => removeFile(index)}
                                        className="p-1 rounded hover:bg-slate-700 transition-colors"
                                    >
                                        <span className="material-symbols-outlined text-slate-400 text-[20px]">close</span>
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Upload Button */}
            {files.some((f) => f.status === "pending") && (
                <button
                    onClick={uploadFiles}
                    disabled={isUploading}
                    className="w-full py-3 px-4 rounded-lg bg-[#135bec] text-white font-medium hover:bg-[#135bec]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                    {isUploading ? (
                        <>
                            <span className="material-symbols-outlined animate-spin">progress_activity</span>
                            Procesando...
                        </>
                    ) : (
                        <>
                            <span className="material-symbols-outlined">cloud_upload</span>
                            Procesar {files.filter((f) => f.status === "pending").length} CV(s)
                        </>
                    )}
                </button>
            )}
        </div>
    );
}
