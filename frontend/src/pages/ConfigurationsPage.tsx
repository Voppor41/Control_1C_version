import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import { useAccess } from "../auth/session";
import { useAsync, useDebounced, useSubmit } from "../lib/hooks";
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
  TextArea,
  TextInput,
} from "../ui/ui";

const LIMIT = 20;

export function ConfigurationsPage() {
  const { canWrite, isClient } = useAccess();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const filterKey = debounced;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }
  const list = useAsync(
    () => api.listConfigurations({ q: debounced || undefined, limit: LIMIT, offset }),
    [debounced, offset],
  );

  return (
    <>
      <PageHeader
        kicker="Каталог"
        title="Конфигурации"
        lede={
          isClient
            ? "Справочник релизов. Менять его может только сопровождение."
            : "Название, описание и текущий релиз. Версии живут внутри карточки."
        }
        actions={canWrite ? <Button onClick={() => setCreating(true)}>Новая конфигурация</Button> : null}
      />
      <div className="toolbar">
        <Field label="Поиск">
          <TextInput value={q} onChange={(event) => setQ(event.target.value)} placeholder="Название" />
        </Field>
      </div>
      <section className="panel">
        <LoadBlock
          status={list.status}
          error={list.error}
          hasData={Boolean(list.data)}
          onRetry={list.reload}
          isEmpty={list.data?.items.length === 0}
          empty={<EmptyState title="Каталог пуст" text="Добавьте конфигурацию, затем её версии." />}
        >
          <ul className="entries">
            {list.data?.items.map((row) => (
              <li className="entry" key={row.id}>
                <div>
                  <h3>
                    <Link to={`/configurations/${row.id}`}>{row.name}</Link>
                  </h3>
                  <p>{row.description || "Без описания"}</p>
                </div>
                <span className={row.current_version ? "pill ok" : "pill warn"}>
                  {row.current_version ? `Текущая ${row.current_version}` : "Нет текущего релиза"}
                </span>
                <div className="entry-actions">
                  <Link className="btn btn-quiet btn-sm" to={`/configurations/${row.id}`}>
                    Версии
                  </Link>
                </div>
              </li>
            ))}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {creating ? (
        <ConfigurationDialog
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            list.reload();
          }}
        />
      ) : null}
    </>
  );
}

export function ConfigurationDialog({
  initial,
  onClose,
  onSaved,
}: {
  initial?: { id: string; name: string; description: string | null };
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      submit.setError(new ApiError(0, "Укажите название", { name: "Укажите название" }));
      return;
    }
    const ok = await submit.run(async () => {
      const payload = { name: name.trim(), description: description.trim() || null };
      if (initial) await api.updateConfiguration(initial.id, payload);
      else await api.createConfiguration(payload);
    });
    if (ok) {
      toast.success(initial ? "Конфигурация сохранена" : "Конфигурация создана");
      onSaved();
    }
  }

  return (
    <Modal title={initial ? "Конфигурация" : "Новая конфигурация"} onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && !submit.error.fieldErrors.name ? <Banner>{submit.error.detail}</Banner> : null}
        <Field label="Название" error={submit.error?.fieldErrors.name}>
          <TextInput value={name} maxLength={255} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Field label="Описание" error={submit.error?.fieldErrors.description}>
          <TextArea value={description} onChange={(event) => setDescription(event.target.value)} />
        </Field>
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            {submit.pending ? "Сохраняем…" : "Сохранить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
