import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { ClientConfigurationRead, UpdateStatus } from "../api/types";
import { useAccess } from "../auth/session";
import { formatSlot } from "../lib/format";
import { useAsync, useDebounced, useSubmit } from "../lib/hooks";
import { STATUS_ORDER, statusLabel } from "../lib/labels";
import { SlotPicker } from "../ui/slot-picker";
import { useToast } from "../ui/toast";
import {
  Banner,
  Button,
  EmptyState,
  Field,
  LoadBlock,
  Modal,
  PageHeader,
  Pager,
  Segmented,
  StatusPill,
  TextArea,
  TextInput,
} from "../ui/ui";

const LIMIT = 20;

export function UpdatesPage() {
  const { canBook, isClient } = useAccess();
  const [params] = useSearchParams();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const [status, setStatus] = useState<UpdateStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(Boolean(params.get("installation")) || isClient);
  const filterKey = `${debounced}|${status}`;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }
  const list = useAsync(
    () =>
      api.listUpdates({
        q: debounced || undefined,
        status: status || undefined,
        limit: LIMIT,
        offset,
      }),
    [debounced, status, offset],
  );

  return (
    <>
      <PageHeader
        kicker="Работы"
        title="Обновления"
        lede={
          isClient
            ? "Запросите обновление и выберите свободное окно."
            : "Запросы клиентов, назначенные даты и смена статуса."
        }
        actions={
          canBook && !isClient ? (
            <Button onClick={() => setCreating(true)}>Запросить</Button>
          ) : null
        }
      />
      {isClient && canBook ? (
        <section className="panel">
          <h2>Запись</h2>
          <RequestForm preset={params.get("installation")} onCreated={list.reload} />
        </section>
      ) : null}
      <div className="toolbar">
        {!isClient ? (
          <Field label="Поиск">
            <TextInput value={q} onChange={(event) => setQ(event.target.value)} placeholder="Организация" />
          </Field>
        ) : null}
        <Segmented
          label="Статус"
          value={status || "all"}
          onChange={(value) => setStatus(value === "all" ? "" : (value as UpdateStatus))}
          options={[
            { value: "all", label: "Все" },
            ...STATUS_ORDER.map((code) => ({ value: code, label: statusLabel(code) })),
          ]}
        />
      </div>
      <section className="panel">
        <LoadBlock
          status={list.status}
          error={list.error}
          hasData={Boolean(list.data)}
          onRetry={list.reload}
          isEmpty={list.data?.items.length === 0}
          empty={<EmptyState title="Обновлений нет" text="Запрос появится, когда клиент или специалист выберет базу." />}
        >
          <ul className="entries">
            {list.data?.items.map((item) => (
              <li className="entry" key={item.id}>
                <div>
                  <h3>
                    <Link to={`/updates/${item.id}`}>{item.configuration_name}</Link>
                  </h3>
                  <p>
                    {item.company_name}
                    {item.infobase_name ? ` · ${item.infobase_name}` : ""} · {formatSlot(item.slot_date, item.slot_start, item.slot_end)}
                  </p>
                </div>
                <p className="mono">
                  {item.source_version ?? "—"} → {item.target_version ?? "—"}
                </p>
                <StatusPill status={item.status} />
              </li>
            ))}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {creating && !isClient ? (
        <Modal title="Запросить обновление" onClose={() => setCreating(false)} wide>
          <RequestForm
            preset={params.get("installation")}
            onCreated={() => {
              setCreating(false);
              list.reload();
            }}
          />
        </Modal>
      ) : null}
    </>
  );
}

export function RequestForm({ preset, onCreated }: { preset?: string | null; onCreated: () => void }) {
  const toast = useToast();
  const submit = useSubmit();
  const { isClient } = useAccess();
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query, 250);
  const installations = useAsync(
    () => api.listInstallations({ q: debounced || undefined, limit: 30 }),
    [debounced],
  );
  const [installationId, setInstallationId] = useState(preset ?? "");
  const [slotId, setSlotId] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const items = installations.data?.items ?? [];
  const selected = items.find((item) => item.id === installationId);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!installationId) {
      submit.setError(new ApiError(0, "Выберите базу", { client_configuration_id: "Выберите базу" }));
      return;
    }
    const ok = await submit.run(async () => {
      const created = await api.createUpdate({
        client_configuration_id: installationId,
        slot_id: slotId,
        comment: comment.trim() || null,
      });
      toast.success(created.slot_id ? "Обновление назначено" : "Запрос отправлен");
    });
    if (ok) onCreated();
  }

  return (
    <form className="stack" onSubmit={onSubmit}>
      {submit.error && !submit.error.fieldErrors.client_configuration_id ? <Banner>{submit.error.detail}</Banner> : null}
      {isClient ? null : (
        <Field label="Поиск базы">
          <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Клиент или конфигурация" />
        </Field>
      )}
      <Field label="База" error={submit.error?.fieldErrors.client_configuration_id}>
        {installations.status === "error" ? <Banner>{installations.error?.detail ?? "Не удалось загрузить базы"}</Banner> : null}
        <div className="choice-grid">
          {items.map((item) => (
            <InstallationChoice
              key={item.id}
              item={item}
              active={installationId === item.id}
              onClick={() => setInstallationId(item.id)}
            />
          ))}
        </div>
        {items.length === 0 && installations.status === "ready" ? <p className="field-hint">Баз не найдено.</p> : null}
        {selected ? null : preset ? <p className="field-hint">Выбранная база подставится, если она есть в списке.</p> : null}
      </Field>
      <Field label="Дата">
        <SlotPicker value={slotId} onChange={setSlotId} allowEmpty />
      </Field>
      <Field label="Комментарий">
        <TextArea value={comment} maxLength={4000} onChange={(event) => setComment(event.target.value)} />
      </Field>
      <div className="form-actions">
        <Button type="submit" disabled={submit.pending}>
          {submit.pending ? "Отправляем…" : slotId ? "Записаться" : "Запросить без даты"}
        </Button>
      </div>
    </form>
  );
}

function InstallationChoice({
  item,
  active,
  onClick,
}: {
  item: ClientConfigurationRead;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className={active ? "choice is-on" : "choice"} onClick={onClick}>
      <b>{item.configuration_name}</b>
      <small>
        {item.company_name} · {item.installed_version}
        {item.current_version ? ` → ${item.current_version}` : ""}
      </small>
    </button>
  );
}
