import { useState } from "react";
import { api } from "../api/client";
import type { ClientRead, ConfigurationRead, UserRead } from "../api/types";
import { useAsync, useDebounced } from "../lib/hooks";
import { Field, Select, TextInput } from "./ui";

export function ClientSelect({
  value,
  onChange,
  label = "Организация",
  error,
  allowEmpty = false,
  emptyLabel = "Не выбрано",
  selectedLabel,
}: {
  value: string;
  onChange: (id: string) => void;
  label?: string;
  error?: string;
  allowEmpty?: boolean;
  emptyLabel?: string;
  selectedLabel?: string;
}) {
  const [q, setQ] = useState("");
  const debounced = useDebounced(q, 250);
  const list = useAsync(() => api.listClients({ q: debounced || undefined, limit: 50 }), [debounced]);
  const items = list.data?.items ?? [];
  const missing = Boolean(value) && !items.some((item) => item.id === value);

  return (
    <Field label={label} error={error ?? (list.status === "error" ? list.error?.detail : undefined)}>
      <TextInput
        value={q}
        onChange={(event) => setQ(event.target.value)}
        placeholder="Поиск по названию, почте или телефону"
        aria-label="Поиск организации"
      />
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        {allowEmpty ? <option value="">{emptyLabel}</option> : <option value="">Выберите организацию</option>}
        {missing ? <option value={value}>{selectedLabel || "Выбранная организация"}</option> : null}
        {items.map((client: ClientRead) => (
          <option key={client.id} value={client.id}>
            {client.company_name}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function SpecialistSelect({
  value,
  onChange,
  error,
}: {
  value: string;
  onChange: (id: string) => void;
  error?: string;
}) {
  const list = useAsync(
    () => api.listUsers({ role: "specialist", is_active: true, limit: 100 }),
    [],
  );
  const items = list.data?.items ?? [];
  return (
    <Field
      label="Специалист"
      hint="Окно принадлежит специалисту сопровождения."
      error={error ?? (list.status === "error" ? list.error?.detail : undefined)}
    >
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Выберите специалиста</option>
        {items.map((user: UserRead) => (
          <option key={user.id} value={user.id}>
            {user.full_name}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function ConfigurationSelect({
  value,
  onChange,
  error,
}: {
  value: string;
  onChange: (id: string) => void;
  error?: string;
}) {
  const [q, setQ] = useState("");
  const debounced = useDebounced(q, 250);
  const list = useAsync(
    () => api.listConfigurations({ q: debounced || undefined, limit: 50 }),
    [debounced],
  );
  const items = list.data?.items ?? [];
  return (
    <Field label="Конфигурация" error={error ?? (list.status === "error" ? list.error?.detail : undefined)}>
      <TextInput
        value={q}
        onChange={(event) => setQ(event.target.value)}
        placeholder="Поиск по названию"
        aria-label="Поиск конфигурации"
      />
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Выберите конфигурацию</option>
        {items.map((row: ConfigurationRead) => (
          <option key={row.id} value={row.id}>
            {row.name}
            {row.current_version ? ` · ${row.current_version}` : ""}
          </option>
        ))}
      </Select>
    </Field>
  );
}
