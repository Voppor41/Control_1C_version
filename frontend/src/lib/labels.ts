import type { RoleCode, UpdateStatus, NotificationType } from "../api/types";

export const ROLE_ORDER: RoleCode[] = ["admin", "specialist", "manager", "client"];

export const STATUS_ORDER: UpdateStatus[] = [
  "requested",
  "scheduled",
  "in_progress",
  "completed",
  "cancelled",
];

export const NOTE_TYPES: NotificationType[] = [
  "update_available",
  "update_scheduled",
  "update_completed",
  "update_cancelled",
];

const ROLES: Record<RoleCode, string> = {
  admin: "Администратор",
  specialist: "Специалист",
  manager: "Руководитель",
  client: "Клиент",
};

const ROLE_LONG: Record<RoleCode, string> = {
  admin: "Администратор",
  specialist: "Специалист по сопровождению",
  manager: "Руководитель отдела сопровождения",
  client: "Клиент",
};

const STATUSES: Record<UpdateStatus, string> = {
  requested: "Запрошено",
  scheduled: "Назначено",
  in_progress: "В работе",
  completed: "Выполнено",
  cancelled: "Отменено",
};

const STATUS_ACTIONS: Record<UpdateStatus, string> = {
  requested: "Вернуть в запрос",
  scheduled: "Назначить",
  in_progress: "Взять в работу",
  completed: "Завершить",
  cancelled: "Отменить",
};

const NOTES: Record<NotificationType, string> = {
  update_available: "Нужно обновление",
  update_scheduled: "Обновление назначено",
  update_completed: "Обновление выполнено",
  update_cancelled: "Обновление отменено",
};

export function roleLabel(role: RoleCode): string {
  return ROLES[role];
}

export function roleLabelLong(role: RoleCode): string {
  return ROLE_LONG[role];
}

export function statusLabel(status: UpdateStatus): string {
  return STATUSES[status];
}

export function statusAction(status: UpdateStatus): string {
  return STATUS_ACTIONS[status];
}

export function noteLabel(type: NotificationType): string {
  return NOTES[type];
}

export const NEXT_STATUS: Record<UpdateStatus, UpdateStatus[]> = {
  requested: ["scheduled", "cancelled"],
  scheduled: ["in_progress", "cancelled", "requested"],
  in_progress: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
};

export function statusTone(status: UpdateStatus): "ok" | "bad" | "warn" | "info" | "muted" {
  if (status === "completed") return "ok";
  if (status === "cancelled") return "muted";
  if (status === "in_progress") return "warn";
  return "info";
}
