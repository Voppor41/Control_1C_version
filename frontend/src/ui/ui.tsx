import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import type { UpdateStatus } from "../api/types";
import { cx } from "../lib/format";
import { useTitle } from "../lib/hooks";
import { statusLabel, statusTone } from "../lib/labels";
import { Mark } from "./icons";

const dialogStack: Array<() => void> = [];

export function Banner({
  children,
  tone = "danger",
}: {
  children: ReactNode;
  tone?: "danger" | "info";
}) {
  return (
    <div className={cx("banner", tone)} role={tone === "danger" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cx("field", className)}>
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="control" {...props} />;
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="control" {...props} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="control" {...props} />;
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "quiet" | "danger" | "light";
  size?: "md" | "sm";
};

export function Button({ tone = "primary", size = "md", className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cx("btn", `btn-${tone}`, size === "sm" && "btn-sm", className)}
      {...props}
    />
  );
}

export function PageHeader({
  kicker,
  title,
  lede,
  actions,
}: {
  kicker?: string;
  title: string;
  lede?: string;
  actions?: ReactNode;
}) {
  useTitle(title);
  return (
    <header className="page-head">
      <div>
        {kicker ? <p className="kicker">{kicker}</p> : null}
        <h1>{title}</h1>
        {lede ? <p className="lede">{lede}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Crumbs({ items }: { items: { to?: string; label: string }[] }) {
  return (
    <nav className="crumbs" aria-label="Навигация">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`}>
          {index > 0 ? <span aria-hidden="true"> / </span> : null}
          {item.to ? <Link to={item.to}>{item.label}</Link> : <span>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function StatusPill({ status }: { status: UpdateStatus }) {
  return <span className={cx("pill", statusTone(status), `st-${status}`)}>{statusLabel(status)}</span>;
}

export function CurrencyPill({ outdated }: { outdated: boolean | null }) {
  if (outdated === null) return <span className="pill warn">Нет текущего релиза</span>;
  if (outdated) return <span className="pill bad">Нужно обновление</span>;
  return <span className="pill ok">Актуально</span>;
}

export function VersionPair({
  installed,
  current,
  outdated,
}: {
  installed: string;
  current: string | null;
  outdated: boolean | null;
}) {
  return (
    <div className="version-pair">
      <span className="mono">{installed}</span>
      <span className="version-arrow" aria-hidden="true">
        →
      </span>
      <span className="mono">{current ?? "—"}</span>
      <CurrencyPill outdated={outdated} />
    </div>
  );
}

export function EmptyState({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true">
        <Mark size={32} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="empty" role="alert">
      <h3>Не удалось загрузить</h3>
      <p>{message}</p>
      {onRetry ? (
        <Button tone="quiet" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </div>
  );
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span className="sk sk-title" />
          <span className="sk sk-meta" />
        </div>
      ))}
    </div>
  );
}

export function Pager({
  total,
  limit,
  offset,
  onOffset,
}: {
  total: number;
  limit: number;
  offset: number;
  onOffset: (next: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <div className="pager">
      <span>
        {from}–{to} из {total}
      </span>
      <div className="inline-actions">
        <Button tone="quiet" size="sm" disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))}>
          Назад
        </Button>
        <span>
          {page} / {pages}
        </span>
        <Button tone="quiet" size="sm" disabled={offset + limit >= total} onClick={() => onOffset(offset + limit)}>
          Дальше
        </Button>
      </div>
    </div>
  );
}

export function Segmented<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
  layer = "base",
  locked = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
  layer?: "base" | "confirm";
  locked?: boolean;
}) {
  const titleId = useId();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!locked) dialogStack.push(onClose);
    const onKey = (event: KeyboardEvent) => {
      if (locked) return;
      if (event.key === "Escape" && dialogStack[dialogStack.length - 1] === onClose) {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    return () => {
      if (!locked) {
        const index = dialogStack.lastIndexOf(onClose);
        if (index >= 0) dialogStack.splice(index, 1);
      }
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [locked, onClose]);

  return createPortal(
    <div
      className={cx("modal-back", layer === "confirm" && "is-top")}
      onClick={() => {
        if (!locked) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        className={cx("modal", wide && "wide")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Закрыть" disabled={locked}>
            ×
          </button>
        </header>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function LoadBlock({
  status,
  error,
  hasData,
  onRetry,
  empty,
  isEmpty,
  children,
}: {
  status: "loading" | "ready" | "error";
  error?: { detail: string } | undefined;
  hasData: boolean;
  onRetry?: () => void;
  empty?: ReactNode;
  isEmpty?: boolean;
  children: ReactNode;
}) {
  if (status === "loading" && !hasData) return <SkeletonList />;
  if (status === "error" && !hasData) {
    return <ErrorState message={error?.detail ?? "Не удалось загрузить данные"} onRetry={onRetry} />;
  }
  return (
    <>
      {status === "error" && error ? <Banner>{error.detail}</Banner> : null}
      {isEmpty ? empty : children}
    </>
  );
}
