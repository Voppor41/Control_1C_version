import { useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { SlotRead } from "../api/types";
import { useAccess, useAuth } from "../auth/session";
import { formatDate, formatTime, todayISO } from "../lib/format";
import { useAsync, useSubmit } from "../lib/hooks";
import { SpecialistSelect } from "../ui/pickers";
import { useToast } from "../ui/toast";
import { Banner, Button, EmptyState, Field, LoadBlock, Modal, PageHeader, Pager, TextInput } from "../ui/ui";

const LIMIT = 20;

export function SlotsPage() {
  const { canWrite, canAdmin } = useAccess();
  const { user } = useAuth();
  const toast = useToast();
  const [from, setFrom] = useState(todayISO());
  const [to, setTo] = useState("");
  const [active, setActive] = useState<"all" | "yes" | "no">("yes");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<SlotRead | null>(null);
  const filterKey = `${from}|${to}|${active}`;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }

  const list = useAsync(
    () =>
      api.listSlots({
        date_from: from || undefined,
        date_to: to || undefined,
        is_active: active === "all" ? undefined : active === "yes",
        limit: LIMIT,
        offset,
      }),
    [from, to, active, offset],
  );

  async function toggle(slot: SlotRead) {
    try {
      await api.updateSlot(slot.id, { is_active: !slot.is_active });
      toast.success(slot.is_active ? "Окно закрыто" : "Окно снова открыто");
      list.reload();
    } catch (error) {
      toast.error(error);
    }
  }

  return (
    <>
      <PageHeader
        kicker="Расписание"
        title="Окна записи"
        lede="День, время и число мест. Клиент видит только свободные будущие окна."
        actions={canWrite ? <Button onClick={() => setCreating(true)}>Открыть окно</Button> : null}
      />
      <div className="toolbar">
        <Field label="С">
          <TextInput type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label="По">
          <TextInput type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </Field>
        <Field label="Состояние">
          <select className="control" value={active} onChange={(event) => setActive(event.target.value as "all" | "yes" | "no")}>
            <option value="yes">Открытые</option>
            <option value="no">Закрытые</option>
            <option value="all">Все</option>
          </select>
        </Field>
      </div>
      <section className="panel">
        <LoadBlock
          status={list.status}
          error={list.error}
          hasData={Boolean(list.data)}
          onRetry={list.reload}
          isEmpty={list.data?.items.length === 0}
          empty={<EmptyState title="Окон нет" text="Откройте день и время, на которые можно записать обновление." />}
        >
          <ul className="entries">
            {list.data?.items.map((slot) => {
              const mine = canAdmin || slot.specialist_id === user?.id;
              return (
                <li className="entry" key={slot.id}>
                  <div>
                    <h3>{formatDate(slot.slot_date)}</h3>
                    <p>
                      {formatTime(slot.start_time)}–{formatTime(slot.end_time)} · {slot.specialist_name}
                    </p>
                  </div>
                  <p className="meta">
                    {slot.booked} из {slot.capacity} · свободно {slot.remaining}
                  </p>
                  <div className="version-pair">
                    <span className={slot.is_active ? "pill ok" : "pill muted"}>{slot.is_active ? "Открыто" : "Закрыто"}</span>
                    {canWrite && mine ? (
                      <div className="entry-actions">
                        <Button size="sm" tone="quiet" onClick={() => setEditing(slot)}>
                          Места
                        </Button>
                        <Button size="sm" tone="quiet" onClick={() => toggle(slot)}>
                          {slot.is_active ? "Закрыть" : "Открыть"}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {creating ? (
        <CreateSlot
          requireSpecialist={canAdmin}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            list.reload();
          }}
        />
      ) : null}
      {editing ? (
        <CapacityDialog
          slot={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            list.reload();
          }}
        />
      ) : null}
    </>
  );
}

function CreateSlot({
  requireSpecialist,
  onClose,
  onCreated,
}: {
  requireSpecialist: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const [date, setDate] = useState(todayISO());
  const [start, setStart] = useState("10:00");
  const [end, setEnd] = useState("12:00");
  const [capacity, setCapacity] = useState("1");
  const [specialistId, setSpecialistId] = useState("");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!date) errors.slot_date = "Укажите дату";
    if (!start) errors.start_time = "Укажите начало";
    if (!end) errors.end_time = "Укажите окончание";
    if (start && end && end <= start) errors.end_time = "Время окончания должно быть позже начала";
    const seats = Number(capacity);
    if (!Number.isInteger(seats) || seats < 1 || seats > 20) errors.capacity = "От 1 до 20";
    if (requireSpecialist && !specialistId) errors.specialist_id = "Выберите специалиста";
    if (Object.keys(errors).length) {
      submit.setError(new ApiError(0, "Проверьте окно", errors));
      return;
    }
    const ok = await submit.run(async () => {
      await api.createSlot({
        slot_date: date,
        start_time: start,
        end_time: end,
        capacity: seats,
        specialist_id: requireSpecialist ? specialistId : undefined,
      });
    });
    if (ok) {
      toast.success("Окно открыто");
      onCreated();
    }
  }

  const past = Boolean(date) && date < todayISO();

  return (
    <Modal title="Новое окно" onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && Object.keys(submit.error.fieldErrors).length === 0 ? <Banner>{submit.error.detail}</Banner> : null}
        {past ? <Banner tone="info">Прошедшая дата не попадёт в список доступных для записи.</Banner> : null}
        <div className="form-grid">
          <Field label="Дата" error={submit.error?.fieldErrors.slot_date} className="span-2">
            <TextInput type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </Field>
          <Field label="Начало" error={submit.error?.fieldErrors.start_time}>
            <TextInput type="time" value={start} onChange={(event) => setStart(event.target.value)} />
          </Field>
          <Field label="Окончание" error={submit.error?.fieldErrors.end_time}>
            <TextInput type="time" value={end} onChange={(event) => setEnd(event.target.value)} />
          </Field>
          <Field label="Мест" error={submit.error?.fieldErrors.capacity}>
            <TextInput
              type="number"
              min={1}
              max={20}
              value={capacity}
              onChange={(event) => setCapacity(event.target.value)}
            />
          </Field>
        </div>
        {requireSpecialist ? (
          <SpecialistSelect
            value={specialistId}
            onChange={setSpecialistId}
            error={submit.error?.fieldErrors.specialist_id}
          />
        ) : (
          <p className="field-hint">Окно откроется на ваше имя.</p>
        )}
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            {submit.pending ? "Сохраняем…" : "Открыть"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function CapacityDialog({ slot, onClose, onSaved }: { slot: SlotRead; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const submit = useSubmit();
  const [capacity, setCapacity] = useState(String(slot.capacity));

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const seats = Number(capacity);
    if (!Number.isInteger(seats) || seats < 1 || seats > 20) {
      submit.setError(new ApiError(0, "От 1 до 20", { capacity: "От 1 до 20" }));
      return;
    }
    const ok = await submit.run(async () => {
      await api.updateSlot(slot.id, { capacity: seats });
    });
    if (ok) {
      toast.success("Вместимость обновлена");
      onSaved();
    }
  }

  return (
    <Modal title="Число мест" onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && !submit.error.fieldErrors.capacity ? <Banner>{submit.error.detail}</Banner> : null}
        <p className="lede">
          {formatDate(slot.slot_date)}, {formatTime(slot.start_time)}–{formatTime(slot.end_time)}. Уже записано: {slot.booked}.
        </p>
        <Field label="Вместимость" error={submit.error?.fieldErrors.capacity}>
          <TextInput type="number" min={1} max={20} value={capacity} onChange={(event) => setCapacity(event.target.value)} />
        </Field>
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            Сохранить
          </Button>
        </div>
      </form>
    </Modal>
  );
}
