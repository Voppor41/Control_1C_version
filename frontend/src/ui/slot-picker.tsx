import { useState } from "react";
import { api } from "../api/client";
import type { AvailableDate, SlotRead } from "../api/types";
import { formatDate, formatTime, plural } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { Banner, EmptyState, SkeletonList } from "./ui";

export function SlotPicker({
  value,
  onChange,
  allowEmpty = false,
}: {
  value: string | null;
  onChange: (slotId: string | null) => void;
  allowEmpty?: boolean;
}) {
  const dates = useAsync(() => api.availableDates(), []);
  const [day, setDay] = useState<string | null>(null);
  const slots = useAsync(() => {
    if (!day) return Promise.resolve({ items: [] as SlotRead[], total: 0, limit: 50, offset: 0 });
    return api.listSlots({ available_only: true, date_from: day, date_to: day, limit: 50 });
  }, [day]);

  if (dates.status === "loading" && !dates.data) return <SkeletonList rows={3} />;
  if (dates.status === "error" && !dates.data) {
    return <Banner>{dates.error?.detail ?? "Не удалось загрузить даты"}</Banner>;
  }

  const items = dates.data ?? [];
  if (items.length === 0) {
    return (
      <EmptyState
        title="Свободных окон нет"
        text="Специалист ещё не открыл запись на ближайшие дни, либо все места заняты."
      />
    );
  }

  return (
    <div className="stack">
      <div className="choice-grid" role="listbox" aria-label="Доступные даты">
        {allowEmpty ? (
          <button
            type="button"
            className={value === null && !day ? "choice is-on" : "choice"}
            onClick={() => {
              setDay(null);
              onChange(null);
            }}
          >
            <b>Без даты</b>
            <small>Только запрос</small>
          </button>
        ) : null}
        {items.map((item: AvailableDate) => (
          <button
            type="button"
            key={item.slot_date}
            className={day === item.slot_date ? "choice is-on" : "choice"}
            onClick={() => setDay(item.slot_date)}
          >
            <b>{formatDate(item.slot_date)}</b>
            <small>
              {item.open_slots} {plural(item.open_slots, "окно", "окна", "окон")} · свободно {item.remaining_capacity}
            </small>
          </button>
        ))}
      </div>
      {day ? (
        slots.status === "loading" && !slots.data ? (
          <SkeletonList rows={2} />
        ) : slots.status === "error" ? (
          <Banner>{slots.error?.detail ?? "Не удалось загрузить окна"}</Banner>
        ) : (
          <div className="choice-grid" role="listbox" aria-label="Окна на выбранный день">
            {(slots.data?.items ?? []).map((slot) => (
              <button
                type="button"
                key={slot.id}
                className={value === slot.id ? "choice is-on" : "choice"}
                onClick={() => onChange(slot.id)}
              >
                <b>
                  {formatTime(slot.start_time)}–{formatTime(slot.end_time)}
                </b>
                <small>
                  {slot.specialist_name} · свободно {slot.remaining}
                </small>
              </button>
            ))}
          </div>
        )
      ) : null}
    </div>
  );
}
