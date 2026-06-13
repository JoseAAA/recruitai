/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    reactStrictMode: true,
    // El frontend llama a la API same-origin (/api) para funcionar igual en
    // localhost y en el servidor detrás de nginx. Este rewrite hace que el
    // acceso DIRECTO al dev server (http://localhost:3000, sin nginx) también
    // funcione: Next reenvía /api/* al backend dentro de la red Docker.
    // BACKEND_INTERNAL_URL se define en docker-compose; fuera de Docker cae
    // a localhost:8000 (npm run dev en el host).
    async rewrites() {
        const backend = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
        return [
            {
                source: "/api/:path*",
                destination: `${backend}/api/:path*`,
            },
        ];
    },
};

module.exports = nextConfig;
