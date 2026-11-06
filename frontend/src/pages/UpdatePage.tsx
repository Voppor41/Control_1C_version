import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { UpdateStatus } from "../api/types";
import { useAccess } from "../auth/session";
import { formatDateTime, formatSlot } from "../lib/format";
import { useAsync, useSubmit } from "../lib/hooks";
import { NEXT_STATUS, statusAction, statusLabel } from "../lib/labels";
import { useConfirm } from "../ui/confirm";
import { SlotPicker } from "../ui/slot-picker";
import { useToast } from "../ui/toast";
import { Banner, Button, Crumbs, ErrorState, Field, PageHeader, SkeletonList, StatusPill, TextArea } from "../ui/ui";

export function UpdatePage() {
  const { updateId = "" } = useParams();
  const { canWrite, canBook } = useAccess();
  const toast = useToast();
  const confirm = useConfirm();
  const submit = useSubmit();
  const [comment, setComment] = useState("");
  const [slotId, setSlotId] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const detail = useAsync(() => api.getUpdate(updateId), [updateId]);

  if (detail.status === "loading" && !detail.data) return <SkeletonList rows={5} />;
  if (!detail.data) {
    return <ErrorState message={detail.error?.detail ?? "Обновление не найдено"} onRetry={detail.reload} />;
  }
  const row = detail.data;
  const history = [...row.status_history].sort((a, b) => a.changed_at.localeCompare(b.changed_at));
  const next = NEXT_STATUS[row.status];
  const canEditSlot = canBook && (row.status === "requested" || row.status === "scheduled");

  async function change(status: UpdateStatus) {
    const hints: Partial<Record<UpdateStatus, string>> = {
      completed: "Установленная версия базы будет заменена на целевой релиз. Клиент получит уведомление.",
      cancelled: "Работа будет отменена, клиент получит уведомление.",
      scheduled: "Клиент получит уведомление о дате. Нужно выбранное окно.",
      requested: "Дата будет снята, обновление снова станет запросом.",
      in_progress: "Работа перейдёт в выполнение.",
    };
    const ok = await confirm({
      title: statusAction(status),
      body: hints[status] ?? "Статус будет изменён.",
      confirmLabel: statusAction(status),
      tone: status === "cancelled" ? "danger" : "primary",
    });
    if (!ok) return;
    const saved = await submit.run(async () => {
      await api.changeUpdateStatus(row.id, { status, comment: comment.trim() || null });
    });
    if (saved) {
      toast.success(`Статус: ${statusLabel(status)}`);
      setComment("");
      detail.reload();
    }
  }

  async function saveSlot() {
    if (!slotId) {
      toast.error(new Error("Выберите окно"));
      return;
    }
    const ok = await submit.run(async () => {
      await api.patchUpdate(row.id, { slot_id: slotId, comment: comment.trim() || null });
    });
    if (ok) {
      toast.success("Дата сохранена");
      setPicking(false);
      setComment("");
      detail.reload();
    }
  }

  async function saveComment() {
    const ok = await submit.run(async () => {
      await api.patchUpdate(row.id, { comment: comment.trim() || null });
    });
    if (ok) {
      toast.success("Комментарий сохранён");
      detail.reload();
    }
  }

  return (
    <>
      <Crumbs items={[{ to: "/updates", label: "Обновления" }, { label: row.configuration_name }]} />
      <PageHeader
        kicker={row.company_name}
        title={row.configuration_name}
        lede={formatSlot(row.slot_date, row.slot_start, row.slot_end)}
        actions={<StatusPill status={row.status} />}
      />
      {submit.error ? <Banner>{submit.error.detail}</Banner> : null}
      <section className="facts">
        <div>
          <span>Откуда</span>
          <b className="mono">{row.source_version ?? "—"}</b>
        </div>
        <div>
          <span>Куда</span>
          <b className="mono">{row.target_version ?? "—"}</b>
        </div>
        <div>
          <span>Специалист</span>
          <b>{row.assigned_specialist_name || "Не назначен"}</b>
        </div>
        <div>
          <span>Запросил</span>
          <b>{row.requested_by_name}</b>
        </div>
      </section>
      <div className="split">
        <section className="panel">
          <h2>История статуса</h2>
          {history.length === 0 ? <p className="meta">Событий пока нет.</p> : null}
          <ol className="timeline">
            {history.map((event) => (
              <li key={event.id}>
                <span className="dot" aria-hidden="true" />
                <div className="stem">
                  <strong>
                    {event.old_status ? `${statusLabel(event.old_status)} → ` : ""}
                    {statusLabel(event.new_status)}
                  </strong>
                  <p className="meta">
                    {formatDateTime(event.changed_at)} · {event.changed_by_name}
                  </p>
                  {event.comment ? <p>{event.comment}</p> : null}
                </div>
              </li>
            ))}
          </ol>
        </section>
        <section className="panel">
          <h2>Действия</h2>
          <p className="lede">{row.comment || "Комментария нет."}</p>
          <p className="meta">
            База: {row.infobase_name || "без имени"} ·{" "}
            <Link to={`/clients/${row.client_id}`}>{row.company_name}</Link>
          </p>
          {canBook ? (
            <Field label="Комментарий">
              <TextArea value={comment} maxLength={4000} onChange={(event) => setComment(event.target.value)} />
            </Field>
          ) : null}
          {canEditSlot ? (
            <div className="stack" style={{ marginTop: 12 }}>
              <Button tone="quiet" onClick={() => setPicking((value) => !value)}>
                {picking ? "Скрыть даты" : "Выбрать другую дату"}
              </Button>
              {picking ? (
                <>
                  <SlotPicker value={slotId} onChange={setSlotId} />
                  <Button onClick={saveSlot} disabled={submit.pending || !slotId}>
                    Сохранить дату
                  </Button>
                </>
              ) : null}
            </div>
          ) : null}
          {canWrite ? (
            <div className="inline-actions" style={{ marginTop: 16 }}>
              {next.map((status) => (
                <Button
                  key={status}
                  tone={status === "cancelled" ? "danger" : "primary"}
                  disabled={submit.pending || (status === "scheduled" && !row.slot_id)}
                  title={status === "scheduled" && !row.slot_id ? "Сначала выберите окно" : undefined}
                  onClick={() => change(status)}
                >
                  {statusAction(status)}
                </Button>
              ))}
              <Button tone="quiet" onClick={saveComment} disabled={submit.pending || !comment.trim()}>
                Сохранить комментарий
              </Button>
            </div>
          ) : canBook && comment.trim() ? (
            <div className="form-actions">
              <Button tone="quiet" onClick={saveComment} disabled={submit.pending}>
                Сохранить комментарий
              </Button>
            </div>
          ) : null}
          {row.completed_at ? <p className="meta">Завершено {formatDateTime(row.completed_at)}</p> : null}
        </section>
      </div>
    </>
  );
}
