"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { AIProviderContext } from "@/lib/ai";

export function Providers({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 60 * 1000,
                        refetchOnWindowFocus: false,
                    },
                },
            })
    );

    return (
        <QueryClientProvider client={queryClient}>
            <AuthProvider>
                <AIProviderContext>
                    {children}
                </AIProviderContext>
            </AuthProvider>
        </QueryClientProvider>
    );
}
