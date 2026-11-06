import type { UserRead } from "../api/types";

const KEY = "nord.session";

export type StoredSession = {
  token: string;
  expiresAt: number;
  user: UserRead;
};

export function readSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    if (!parsed.token || !parsed.user || typeof parsed.expiresAt !== "number") {
      localStorage.removeItem(KEY);
      return null;
    }
    if (parsed.expiresAt <= Date.now()) {
      localStorage.removeItem(KEY);
      return null;
    }
    return parsed;
  } catch {
    localStorage.removeItem(KEY);
    return null;
  }
}

export function readToken(): string | null {
  return readSession()?.token ?? null;
}

export function writeSession(session: StoredSession) {
  localStorage.setItem(KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(KEY);
}
