"use client";

import { createContext, useContext, useState, useEffect, useRef, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface User {
    id: string;
    email: string;
    full_name: string;
    role: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    sessionWarning: boolean;          // true when < 10 min left
    dismissSessionWarning: () => void;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, fullName: string) => Promise<void>;
    logout: () => void;
}

/** Decode JWT payload without a library — reads the public exp claim only. */
function getTokenExpiry(token: string): number | null {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        return typeof payload.exp === "number" ? payload.exp * 1000 : null; // ms
    } catch {
        return null;
    }
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [sessionWarning, setSessionWarning] = useState(false);
    const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const router = useRouter();

    const scheduleExpiryWarning = (rawToken: string) => {
        if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
        const expiry = getTokenExpiry(rawToken);
        if (!expiry) return;
        const warnAt = expiry - 10 * 60 * 1000; // 10 min before expiry
        const delay = warnAt - Date.now();
        if (delay > 0) {
            warningTimerRef.current = setTimeout(() => setSessionWarning(true), delay);
        } else if (Date.now() < expiry) {
            // Already within the warning window but session still valid
            setSessionWarning(true);
        }
    };

    // Check for existing session on mount
    useEffect(() => {
        const storedToken = localStorage.getItem("token");
        if (storedToken) {
            setToken(storedToken);
            fetchUser(storedToken);
            scheduleExpiryWarning(storedToken);
        } else {
            setIsLoading(false);
        }
        return () => {
            if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
        };
    }, []);

    const fetchUser = async (token: string) => {
        try {
            api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
            const response = await api.get("/auth/me");
            setUser(response.data);
        } catch (error) {
            localStorage.removeItem("token");
            delete api.defaults.headers.common["Authorization"];
        } finally {
            setIsLoading(false);
        }
    };

    const login = async (email: string, password: string) => {
        const response = await api.post("/auth/login/json", { email, password });
        const { access_token } = response.data;

        localStorage.setItem("token", access_token);
        setToken(access_token);
        setSessionWarning(false);
        api.defaults.headers.common["Authorization"] = `Bearer ${access_token}`;

        scheduleExpiryWarning(access_token);
        await fetchUser(access_token);
        router.push("/");
    };

    const register = async (email: string, password: string, fullName: string) => {
        await api.post("/auth/register", {
            email,
            password,
            full_name: fullName,
        });

        // Auto-login after registration
        await login(email, password);
    };

    const dismissSessionWarning = () => setSessionWarning(false);

    const logout = () => {
        if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
        localStorage.removeItem("token");
        delete api.defaults.headers.common["Authorization"];
        setToken(null);
        setUser(null);
        setSessionWarning(false);
        router.push("/login");
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                isLoading,
                isAuthenticated: !!user,
                sessionWarning,
                dismissSessionWarning,
                login,
                register,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
