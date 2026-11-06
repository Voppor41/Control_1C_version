import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, asApiError } from "../api/errors";

export type AsyncState<T> = {
  status: "loading" | "ready" | "error";
  data?: T;
  error?: ApiError;
};

export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[]) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });

  useEffect(() => {
    const id = ++seq.current;
    let active = true;
    setState((prev) => ({ status: "loading", data: prev.data }));
    fnRef.current().then(
      (data) => {
        if (!active || seq.current !== id) return;
        setState({ status: "ready", data });
      },
      (error: unknown) => {
        if (!active || seq.current !== id) return;
        if (error instanceof ApiError && error.status === 401) return;
        setState((prev) => ({
          status: "error",
          error: asApiError(error),
          data: prev.data,
        }));
      },
    );
    return () => {
      active = false;
    };
  }, [tick, ...deps]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { ...state, reload };
}

export function useDebounced<T>(value: T, delay = 280): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useTitle(title: string) {
  useEffect(() => {
    document.title = `${title} — Верконт`;
    return () => {
      document.title = "Верконт — учёт версий 1С";
    };
  }, [title]);
}

export function useSubmit() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function run(task: () => Promise<void>): Promise<boolean> {
    setPending(true);
    setError(null);
    try {
      await task();
      return true;
    } catch (caught) {
      setError(asApiError(caught));
      return false;
    } finally {
      setPending(false);
    }
  }

  return { pending, error, setError, run };
}
