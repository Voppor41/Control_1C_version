import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { messageOf } from "../api/errors";

type ToastItem = { id: number; text: string; tone: "ok" | "error" };

type ToastApi = {
  success: (text: string) => void;
  error: (error: unknown) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((text: string, tone: "ok" | "error") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current.slice(-3), { id, text, tone }]);
    window.setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id));
    }, tone === "error" ? 6400 : 4200);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (text) => push(text, "ok"),
      error: (error) => push(messageOf(error), "error"),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toaster" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className={item.tone === "error" ? "toast error" : "toast"} role="status">
            <span>{item.text}</span>
            <button
              type="button"
              aria-label="Закрыть уведомление"
              onClick={() => setItems((current) => current.filter((row) => row.id !== item.id))}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const value = useContext(ToastContext);
  if (!value) throw new Error("ToastProvider is missing");
  return value;
}
