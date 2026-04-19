import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
    title: "RecruitAI-Core | Sistema de Reclutamiento con IA",
    description: "Sistema de adquisición de talento con IA, búsqueda semántica y scoring explicable",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="es" suppressHydrationWarning>
            <head>
                {/* Apply saved theme before React hydrates — prevents white flash */}
                <script
                    dangerouslySetInnerHTML={{
                        __html: `try{var t=localStorage.getItem('theme');document.documentElement.classList.toggle('dark',t===null||t==='dark')}catch(e){}`,
                    }}
                />
                {/* Preconnect for faster font loading */}
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                {/* Material Symbols font - must be in head for proper loading */}
                <link
                    href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className={`${inter.className} antialiased`}>
                <Providers>{children}</Providers>
            </body>
        </html>
    );
}
