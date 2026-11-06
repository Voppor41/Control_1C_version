import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { VersionRead } from "../api/types";
import { useAccess } from "../auth/session";
import { formatDate, todayISO } from "../lib/format";
import { useAsync, useSubmit } from "../lib/hooks";
import { useConfirm } from "../ui/confirm";
import { useToast } from "../ui/toast";
import {
  Banner,
  Button,
  Crumbs,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  PageHeader,
  SkeletonList,
  TextArea,
  TextInput,
} from "../ui/ui";
import { ConfigurationDialog } from "./ConfigurationsPage";

export function ConfigurationPage() {
  const { configurationId = "" } = useParams();
  const navigate = useNavigate();
  const { canWrite } = useAccess();
  const toast = useToast();
  const confirm = useConfirm();
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const detail = useAsync(() => api.getConfiguration(configurationId), [configurationId]);

  async function makeCurrent(version: VersionRead) {
    try {
      await api.updateVersion(configurationId, version.id, { is_current: true });
      toast.success(`Текущий релиз: ${version.version}`);
      detail.reload();
    } catch (error) {
      toast.error(error);
    }
  }

  async function removeVersion(version: VersionRead) {
    const ok = await confirm({
      title: `Удалить ${version.version}?`,
      body: "Версию нельзя удалить, если она стоит у клиента или фигурирует в истории обновлений.",
      confirmLabel: "Удалить",
      tone: "danger",
    });
    if (!ok) return;
    try {
      await api.deleteVersion(configurationId, version.id);
      toast.success("Версия удалена");
      detail.reload();
    } catch (error) {
      toast.error(error);
    }
  }

  async function removeConfiguration() {
    if (!detail.data) return;
    const ok = await confirm({
      title: "Удалить конфигурацию?",
      body: "Это возможно, только если её ещё никто не установил.",
      confirmLabel: "Удалить",
      tone: "danger",
    });
    if (!ok) return;
    try {
      await api.deleteConfiguration(detail.data.id);
      toast.success("Конфигурация удалена");
      navigate("/configurations");
    } catch (error) {
      toast.error(error);
    }
  }

  if (detail.status === "loading" && !detail.data) return <SkeletonList rows={4} />;
  if (!detail.data) {
    return <ErrorState message={detail.error?.detail ?? "Конфигурация не найдена"} onRetry={detail.reload} />;
  }
  const row = detail.data;
  const versions = [...row.versions].sort((a, b) => b.version.localeCompare(a.version, "ru"));

  return (
    <>
      <Crumbs items={[{ to: "/configurations", label: "Конфигурации" }, { label: row.name }]} />
      <PageHeader
        kicker="Конфигурация"
        title={row.name}
        lede={row.description || "Без описания"}
        actions={
          canWrite ? (
            <>
              <Button tone="quiet" onClick={() => setEditing(true)}>
                Изменить
              </Button>
              <Button onClick={() => setAdding(true)}>Новая версия</Button>
              <Button tone="danger" onClick={removeConfiguration}>
                Удалить
              </Button>
            </>
          ) : null
        }
      />
      <section className="panel">
        <div className="panel-head">
          <h2>Версии</h2>
          <p className="meta">Текущий релиз сравнивается с тем, что стоит у клиента.</p>
        </div>
        {versions.length === 0 ? (
          <EmptyState title="Версий нет" text="Первая добавленная версия станет текущей автоматически." />
        ) : (
          <ul className="entries">
            {versions.map((version) => {
              const blocked = version.is_current && versions.length > 1;
              return (
                <li className="entry" key={version.id}>
                  <div>
                    <h3 className="mono">{version.version}</h3>
                    <p>
                      {version.released_at ? formatDate(version.released_at) : "Дата выпуска не указана"}
                      {version.notes ? ` · ${version.notes}` : ""}
                    </p>
                  </div>
                  <span className={version.is_current ? "pill ok" : "pill muted"}>
                    {version.is_current ? "Текущая" : "Архив"}
                  </span>
                  {canWrite ? (
                    <div className="entry-actions">
                      {version.is_current ? null : (
                        <Button size="sm" tone="quiet" onClick={() => makeCurrent(version)}>
                          Сделать текущей
                        </Button>
                      )}
                      <Button
                        size="sm"
                        tone="danger"
                        disabled={blocked}
                        title={blocked ? "Сначала назначьте другую версию текущей" : undefined}
                        onClick={() => removeVersion(version)}
                      >
                        Удалить
                      </Button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
      {editing ? (
        <ConfigurationDialog
          initial={row}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            detail.reload();
          }}
        />
      ) : null}
      {adding ? (
        <VersionDialog
          configurationId={row.id}
          first={versions.length === 0}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            detail.reload();
          }}
        />
      ) : null}
    </>
  );
}

function VersionDialog({
  configurationId,
  first,
  onClose,
  onSaved,
}: {
  configurationId: string;
  first: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const [version, setVersion] = useState("");
  const [released, setReleased] = useState(todayISO());
  const [notes, setNotes] = useState("");
  const [current, setCurrent] = useState(true);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!version.trim()) {
      submit.setError(new ApiError(0, "Укажите номер версии", { version: "Укажите номер версии" }));
      return;
    }
    const ok = await submit.run(async () => {
      await api.createVersion(configurationId, {
        version: version.trim(),
        released_at: released || null,
        is_current: current,
        notes: notes.trim() || null,
      });
    });
    if (ok) {
      toast.success("Версия добавлена");
      onSaved();
    }
  }

  return (
    <Modal title="Новая версия" onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && !submit.error.fieldErrors.version ? <Banner>{submit.error.detail}</Banner> : null}
        <Field label="Номер" error={submit.error?.fieldErrors.version} hint="Например, 3.0.175">
          <TextInput className="control mono" value={version} maxLength={64} onChange={(event) => setVersion(event.target.value)} />
        </Field>
        <Field label="Дата выпуска">
          <TextInput type="date" value={released} onChange={(event) => setReleased(event.target.value)} />
        </Field>
        <Field label="Заметки">
          <TextArea value={notes} onChange={(event) => setNotes(event.target.value)} />
        </Field>
        <label className="check">
          <input type="checkbox" checked={current} onChange={(event) => setCurrent(event.target.checked)} />
          Сделать текущим релизом
        </label>
        {first ? <p className="field-hint">Первая версия станет текущей, даже если флажок снят.</p> : null}
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            {submit.pending ? "Сохраняем…" : "Добавить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
