"use client";

import { DashboardLayout } from "@/components/layout/dashboard-layout";
import SettingsPage from "@/components/settings/SettingsPage";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function SettingsRoute() {
    const { user, isLoading } = useAuth();
    const router = useRouter();
    const [checkComplete, setCheckComplete] = useState(false);

    useEffect(() => {
        // Wait for auth to load
        if (!isLoading) {
            // Redirect non-admin users to home
            if (!user || user.role !== 'admin') {
                router.push('/');
            } else {
                setCheckComplete(true);
            }
        }
    }, [user, isLoading, router]);

    // Don't render if not admin or still checking
    if (isLoading || !checkComplete) {
        return (
            <DashboardLayout>
                <div className="flex items-center justify-center h-64">
                    <div className="text-slate-500">Verificando permisos...</div>
                </div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout>
            <SettingsPage />
        </DashboardLayout>
    );
}
