import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { ClientConfigurationRead } from "../api/types";
import { formatDateTime } from "../lib/format";
import { useAsync, useSubmit } from "../lib/hooks";
import { useAccess } from "../auth/session";
import { useConfirm } from "./confirm";
import { NotifyDialog } from "./notify";
import { useToast } from "./toast";
import { Banner, Button, Field, Modal, Select, TextInput, VersionPair } from "./ui";

export function InstallationCard({
  item,
  onChanged,
  showClient = true,
}: {
  item: ClientConfigurationRead;
  onChanged: () => void;
  showClient?: boolean;
}) {
  const { canWrite, canBook } = useAccess();
  const toast = useToast();
  const confirm = useConfirm();
  const [editing, setEditing] = useState(false);
  const [notifying, setNotifying] = useState(false);
  const [busy, setBusy] = useState(false);

  async function runCheck() {
    setBusy(true);
    try {
      const result = await api.runChecks({ client_configuration_id: item.id });
      const created = result.created[0];
      const skipped = result.skipped[0];
      if (created) {
        toast.success(
          created.is_outdated
            ? `${item.configuration_name}: ${created.installed_version} → ${created.actual_version}`
            : `${item.configuration_name}: релиз актуален`,
        );
      } else if (skipped) {
        toast.error(new ApiError(0, "У конфигурации нет текущего релиза", {}));
      }
      onChanged();
    } catch (error) {
      toast.error(error);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const ok = await confirm({
      title: "Удалить установку?",
      body: "База исчезнет из карточки клиента, если по ней нет истории обновлений.",
      confirmLabel: "Удалить",
      tone: "danger",
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deleteInstallation(item.id);
      toast.success("Установка удалена");
      onChanged();
    } catch (error) {
      toast.error(error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="entry">
      <div>
        <h3>
          {showClient ? (
            <Link to={`/clients/${item.client_id}`}>{item.company_name}</Link>
          ) : (
            item.configuration_name
          )}
        </h3>
        <p>
          {showClient ? item.configuration_name : item.company_name}
          {item.infobase_name ? ` · ${item.infobase_name}` : ""}
          {" · "}
          {item.last_checked_at ? `проверка ${formatDateTime(item.last_checked_at)}` : "проверки ещё не было"}
        </p>
      </div>
      <VersionPair
        installed={item.installed_version}
        current={item.current_version}
        outdated={item.is_outdated}
      />
      <div className="entry-actions">
        {canBook ? (
          <Link className="btn btn-quiet btn-sm" to={`/updates?installation=${item.id}`}>
            Записать
          </Link>
        ) : null}
        {canWrite ? (
          <>
            <Button size="sm" tone="quiet" onClick={runCheck} disabled={busy}>
              Проверить
            </Button>
            <Button size="sm" tone="quiet" onClick={() => setNotifying(true)} disabled={busy}>
              Сообщить
            </Button>
            <Button size="sm" tone="quiet" onClick={() => setEditing(true)} disabled={busy}>
              Версия
            </Button>
            <Button size="sm" tone="danger" onClick={remove} disabled={busy}>
              Удалить
            </Button>
          </>
        ) : null}
      </div>
      {editing ? (
        <EditInstallation
          item={item}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            onChanged();
          }}
        />
      ) : null}
      {notifying ? (
        <NotifyDialog
          clientId={item.client_id}
          clientName={item.company_name}
          installationId={item.id}
          onClose={() => setNotifying(false)}
        />
      ) : null}
    </li>
  );
}

function EditInstallation({
  item,
  onClose,
  onSaved,
}: {
  item: ClientConfigurationRead;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const detail = useAsync(() => api.getConfiguration(item.configuration_id), [item.configuration_id]);
  const [versionId, setVersionId] = useState(item.installed_version_id);
  const [infobase, setInfobase] = useState(item.infobase_name ?? "");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const ok = await submit.run(async () => {
      await api.updateInstallation(item.id, {
        installed_version_id: versionId,
        infobase_name: infobase.trim() || null,
      });
    });
    if (ok) {
      toast.success("Установка обновлена");
      onSaved();
    }
  }

  return (
    <Modal title="Установленная версия" onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error ? <Banner>{submit.error.detail}</Banner> : null}
        <Field label="Версия" error={submit.error?.fieldErrors.installed_version_id}>
          <Select value={versionId} onChange={(event) => setVersionId(event.target.value)}>
            {(detail.data?.versions ?? []).map((version) => (
              <option key={version.id} value={version.id}>
                {version.version}
                {version.is_current ? " · текущая" : ""}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Информационная база" error={submit.error?.fieldErrors.infobase_name}>
          <TextInput
            value={infobase}
            maxLength={255}
            onChange={(event) => setInfobase(event.target.value)}
          />
        </Field>
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending || !versionId}>
            {submit.pending ? "Сохраняем…" : "Сохранить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function AddInstallation({
  clientId,
  onClose,
  onCreated,
}: {
  clientId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const [configurationId, setConfigurationId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [infobase, setInfobase] = useState("");
  const configs = useAsync(() => api.listConfigurations({ limit: 100 }), []);
  const detail = useAsync(() => {
    if (!configurationId) return Promise.resolve(null);
    return api.getConfiguration(configurationId);
  }, [configurationId]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!configurationId || !versionId) {
      submit.setError(new ApiError(0, "Выберите конфигурацию и версию", {
        configuration_id: configurationId ? "" : "Выберите конфигурацию",
        installed_version_id: versionId ? "" : "Выберите версию",
      }));
      return;
    }
    const ok = await submit.run(async () => {
      await api.createInstallation(clientId, {
        configuration_id: configurationId,
        installed_version_id: versionId,
        infobase_name: infobase.trim() || null,
      });
    });
    if (ok) {
      toast.success("Установка добавлена");
      onCreated();
    }
  }

  return (
    <Modal title="Новая установка" onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && !submit.error.fieldErrors.configuration_id && !submit.error.fieldErrors.installed_version_id ? (
          <Banner>{submit.error.detail}</Banner>
        ) : null}
        <Field label="Конфигурация" error={submit.error?.fieldErrors.configuration_id || undefined}>
          <Select
            value={configurationId}
            onChange={(event) => {
              setConfigurationId(event.target.value);
              setVersionId("");
            }}
          >
            <option value="">Выберите конфигурацию</option>
            {(configs.data?.items ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Установленная версия" error={submit.error?.fieldErrors.installed_version_id || undefined}>
          <Select value={versionId} onChange={(event) => setVersionId(event.target.value)} disabled={!configurationId}>
            <option value="">Выберите версию</option>
            {(detail.data?.versions ?? []).map((version) => (
              <option key={version.id} value={version.id}>
                {version.version}
                {version.is_current ? " · текущая" : ""}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Информационная база" hint="Необязательно. Например, romashka_bp.">
          <TextInput value={infobase} maxLength={255} onChange={(event) => setInfobase(event.target.value)} />
        </Field>
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
