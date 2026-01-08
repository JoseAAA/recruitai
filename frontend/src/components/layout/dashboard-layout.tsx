"use client";

import { ReactNode } from "react";
import { ProtectedRoute } from "@/components/auth/protected-route";
import Sidebar from "./Sidebar";
import Header from "./Header";

export function DashboardLayout({ children }: { children: ReactNode }) {
    return (
        <ProtectedRoute>
            <div className="flex h-screen w-full bg-slate-50 dark:bg-[#0f172a] text-slate-900 dark:text-white">
                <Sidebar />
                <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
                    <Header />
                    <div className="flex-1 overflow-y-auto p-4 md:p-8">
                        <div className="max-w-7xl mx-auto flex flex-col gap-8">
                            {children}
                        </div>
                    </div>
                </main>
            </div>
        </ProtectedRoute>
    );
}
