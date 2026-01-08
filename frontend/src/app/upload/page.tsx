import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { CVUploader } from "@/components/upload/cv-uploader";

export default function UploadPage() {
    return (
        <DashboardLayout>
            <div className="max-w-2xl mx-auto">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-white">Subir CVs</h1>
                    <p className="text-slate-400">
                        Sube currículums para análisis con IA e indexación automática
                    </p>
                </div>
                <CVUploader />
            </div>
        </DashboardLayout>
    );
}
