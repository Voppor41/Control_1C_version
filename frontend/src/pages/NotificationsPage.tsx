import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { NotificationType } from "../api/types";
import { useAccess, useAuth } from "../auth/session";
import { formatDateTime } from "../lib/format";
import { useAsync, useSubmit } from "../lib/hooks";
import { NOTE_TYPES, noteLabel } from "../lib/labels";
import { ClientSelect } from "../ui/pickers";
import { useToast } from "../ui/toast";
import { Banner, Button, EmptyState, Field, LoadBlock, Modal, PageHeader, Pager, Segmented, TextArea, TextInput } from "../ui/ui";

const LIMIT = 20;

export function NotificationsPage() {
  const { user } = useAuth();
  const { canWrite, isClient } = useAccess();
  const toast = useToast();
  const [filter, setFilter] = useState<"all" | "unread" | "read">("all");
  const [kind, setKind] = useState<NotificationType | "">("");
  const [offset, setOffset] = useState(0);
  const [composing, setComposing] = useState(false);
  const filterKey = `${filter}|${kind}`;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }
  const list = useAsync(
    () =>
      api.listNotifications({
        is_read: filter === "all" ? undefined : filter === "read",
        type: kind || undefined,
        limit: LIMIT,
        offset,
      }),
    [filter, kind, offset],
  );

  async function mark(id: string) {
    try {
      await api.markNotificationRead(id);
      toast.success("Отмечено прочитанным");
      list.reload();
    } catch (error) {
      toast.error(error);
    }
  }

  return (
    <>
      <PageHeader
        kicker="Почта"
        title="Уведомления"
        lede={
          isClient
            ? "Сообщения сопровождения о нужных и назначенных обновлениях."
            : "Рассылка клиенту. Пустой текст при выбранной базе Норд заполнит сам."
        }
        actions={
          canWrite ? (
            <Button onClick={() => setComposing(true)}>Сообщить клиенту</Button>
          ) : null
        }
      />
      <div className="toolbar">
        <Segmented
          label="Прочтение"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "Все" },
            { value: "unread", label: "Непрочитанные" },
            { value: "read", label: "Прочитанные" },
          ]}
        />
        <Segmented
          label="Тип"
          value={kind || "all"}
          onChange={(value) => setKind(value === "all" ? "" : (value as NotificationType))}
          options={[
            { value: "all", label: "Любой тип" },
            ...NOTE_TYPES.map((type) => ({ value: type, label: noteLabel(type) })),
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
          empty={<EmptyState title="Писем нет" text="Когда сопровождение напишет о релизе, сообщение появится здесь." />}
        >
          <p className="meta" style={{ marginBottom: 8 }}>
            Непрочитанных: {list.data?.unread ?? 0}
          </p>
          <ul className="entries">
            {list.data?.items.map((note) => (
              <li className="entry" key={note.id}>
                <div>
                  <h3>{note.title}</h3>
                  <p>{note.message}</p>
                  <p>
                    {formatDateTime(note.created_at)}
                    {isClient ? "" : ` · ${note.company_name}`}
                    {note.configuration_name ? ` · ${note.configuration_name}` : ""}
                  </p>
                </div>
                <span className={note.is_read ? "pill muted" : "pill warn"}>{note.is_read ? "Прочитано" : noteLabel(note.type)}</span>
                <div className="entry-actions">
                  {note.scheduled_update_id ? (
                    <Link className="btn btn-quiet btn-sm" to={`/updates/${note.scheduled_update_id}`}>
                      Обновление
                    </Link>
                  ) : null}
                  {!note.is_read && user?.id === note.recipient_id ? (
                    <Button size="sm" tone="quiet" onClick={() => mark(note.id)}>
                      Прочитано
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {composing ? <Compose onClose={() => setComposing(false)} onDone={list.reload} /> : null}
    </>
  );
}

function Compose({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const submit = useSubmit();
  const [clientId, setClientId] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!clientId) errors.client_id = "Выберите организацию";
    if (!message.trim()) errors.message = "Укажите текст";
    if (Object.keys(errors).length) {
      submit.setError(new ApiError(0, "Проверьте форму", errors));
      return;
    }
    const ok = await submit.run(async () => {
      const created = await api.createNotification({
        client_id: clientId,
        title: title.trim() || null,
        message: message.trim(),
      });
      toast.success(`Уведомление отправлено: ${created.length}`);
    });
    if (ok) {
      onDone();
      onClose();
    }
  }

  const banner = submit.error && Object.keys(submit.error.fieldErrors).length === 0 ? submit.error.detail : null;

  return (
    <Modal title="Сообщение клиенту" onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {banner ? <Banner>{banner}</Banner> : null}
        <ClientSelect value={clientId} onChange={setClientId} error={submit.error?.fieldErrors.client_id} />
        <Field label="Заголовок">
          <TextInput value={title} maxLength={255} onChange={(event) => setTitle(event.target.value)} />
        </Field>
        <Field label="Текст" hint="Без выбранной базы текст обязателен." error={submit.error?.fieldErrors.message}>
          <TextArea value={message} onChange={(event) => setMessage(event.target.value)} />
        </Field>
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            {submit.pending ? "Отправляем…" : "Отправить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
