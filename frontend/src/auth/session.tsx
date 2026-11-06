import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler } from "../api/client";
import { ApiError } from "../api/errors";
import type { RoleCode, UserRead } from "../api/types";
import { clearSession, readSession, writeSession } from "./storage";

type Status = "loading" | "anon" | "ready";

type AuthValue = {
  status: Status;
  user: UserRead | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<UserRead | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setStatus("anon");
    });
    const stored = readSession();
    if (!stored) {
      setStatus("anon");
      return;
    }
    setUser(stored.user);
    api.me().then(
      (fresh) => {
        writeSession({ token: stored.token, expiresAt: stored.expiresAt, user: fresh });
        setUser(fresh);
        setStatus("ready");
      },
      (error: unknown) => {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearSession();
          setUser(null);
          setStatus("anon");
          return;
        }
        setStatus("ready");
      },
    );
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      status,
      user,
      login: async (email, password) => {
        const token = await api.login({ email: email.trim(), password });
        const expiresAt = Date.now() + token.expires_in * 1000;
        writeSession({ token: token.access_token, expiresAt, user: token.user });
        setUser(token.user);
        setStatus("ready");
      },
      logout: () => {
        clearSession();
        setUser(null);
        setStatus("anon");
      },
    }),
    [status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}

export function useAccess() {
  const { user } = useAuth();
  const role = user?.role ?? null;
  return {
    role,
    user,
    isClient: role === "client",
    canWrite: role === "admin" || role === "specialist",
    canAdmin: role === "admin",
    canReport: role === "admin" || role === "manager",
    canBook: role === "admin" || role === "specialist" || role === "client",
    isStaff: role === "admin" || role === "specialist" || role === "manager",
  };
}

export function hasRole(role: RoleCode | null, roles: readonly RoleCode[]): boolean {
  return role !== null && roles.includes(role);
}
