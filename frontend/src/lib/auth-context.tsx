"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
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
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, fullName: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();

    // Check for existing session on mount
    useEffect(() => {
        const storedToken = localStorage.getItem("token");
        if (storedToken) {
            setToken(storedToken);
            fetchUser(storedToken);
        } else {
            setIsLoading(false);
        }
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
        api.defaults.headers.common["Authorization"] = `Bearer ${access_token}`;

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

    const logout = () => {
        localStorage.removeItem("token");
        delete api.defaults.headers.common["Authorization"];
        setToken(null);
        setUser(null);
        router.push("/login");
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                isLoading,
                isAuthenticated: !!user,
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
