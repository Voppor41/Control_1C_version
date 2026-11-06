import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { Button, Modal } from "./ui";

type ConfirmOptions = {
  title: string;
  body: string;
  confirmLabel?: string;
  tone?: "primary" | "danger";
};

type ConfirmApi = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmApi | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<{
    options: ConfirmOptions;
    resolve: (value: boolean) => void;
  } | null>(null);

  const confirm = useCallback<ConfirmApi>((options) => {
    return new Promise((resolve) => {
      setPending({ options, resolve });
    });
  }, []);

  function close(value: boolean) {
    pending?.resolve(value);
    setPending(null);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {pending ? (
        <Modal title={pending.options.title} onClose={() => close(false)} layer="confirm">
          <p className="lede">{pending.options.body}</p>
          <div className="modal-actions">
            <Button tone="quiet" onClick={() => close(false)}>
              Оставить
            </Button>
            <Button tone={pending.options.tone ?? "danger"} onClick={() => close(true)}>
              {pending.options.confirmLabel ?? "Подтвердить"}
            </Button>
          </div>
        </Modal>
      ) : null}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmApi {
  const value = useContext(ConfirmContext);
  if (!value) throw new Error("ConfirmProvider is missing");
  return value;
}
