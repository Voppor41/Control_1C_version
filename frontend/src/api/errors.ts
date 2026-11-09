import type { RoleCode, UpdateStatus } from "./types";
import { roleLabel, statusLabel } from "../lib/labels";

const DETAILS: Record<string, string> = {
  "Invalid email or password": "Неверная почта или пароль",
  "User is deactivated": "Учётная запись отключена",
  "Not authenticated": "Нужно войти снова",
  "Invalid or expired token": "Сессия истекла. Войдите снова",
  "Inactive or unknown user": "Учётная запись недоступна",
  "Insufficient permissions": "Недостаточно прав для этого действия",
  "User not found": "Пользователь не найден",
  "Client role requires client_id": "Для роли «Клиент» нужно выбрать организацию",
  "Only client users can be linked to a client company":
    "Организацию можно привязать только к пользователю с ролью «Клиент»",
  "Cannot turn an employee into a company user. Register a company user instead.":
    "Нельзя превратить сотрудника в пользователя компании. Зарегистрируйте пользователя компании отдельно.",
  "Cannot assign an employee position to a company user. Register an employee instead.":
    "Нельзя назначить пользователю компании должность сотрудника. Зарегистрируйте сотрудника отдельно.",
  "You cannot deactivate yourself": "Нельзя отключить свою учётную запись",
  "You cannot remove your own administrator role": "Нельзя снять с себя роль администратора",
  "Cannot remove or deactivate the last active administrator":
    "Нельзя отключить или разжаловать последнего активного администратора",
  "User with this email already exists": "Пользователь с такой почтой уже есть",
  "Client not found": "Клиент не найден",
  "Responsible employee must be an active staff user":
    "Ответственный должен быть активным сотрудником",
  "Configuration not found": "Конфигурация не найдена",
  "Client configuration not found": "Установка не найдена",
  "installed_version_id does not belong to the configuration":
    "Выбранная версия не относится к этой конфигурации",
  "Mark another version as current before unsetting this one":
    "Сначала назначьте текущей другую версию",
  "Data conflict": "Такие данные уже используются",
  "You can only access your own client data": "Доступны только данные вашей организации",
  "Client with this name, email, or phone already exists":
    "Клиент с таким названием, почтой или телефоном уже есть",
  "Cannot delete a client that has update history":
    "Нельзя удалить клиента, у которого есть история обновлений",
  "Configuration with this name already exists": "Конфигурация с таким названием уже есть",
  "Configuration is installed for a client": "Конфигурация установлена у клиента и не удаляется",
  "This version already exists": "Такая версия уже есть",
  "Version not found": "Версия не найдена",
  "Version is referenced and cannot be deleted": "Версия используется и не удаляется",
  "Mark another version as current before deleting this one":
    "Сначала назначьте текущей другую версию",
  "This client already has that configuration": "У клиента уже есть эта конфигурация",
  "Cannot delete a configuration that has update history":
    "Нельзя удалить установку, у которой есть история обновлений",
  "Client has no active portal user. Register a user with the client role first.":
    "У клиента нет активного пользователя портала. Сначала создайте пользователя с ролью «Клиент».",
  "Configuration does not belong to this client": "Конфигурация не принадлежит этому клиенту",
  "message is required when client_configuration_id is omitted":
    "Укажите текст, если установка не выбрана",
  "Notification not found": "Уведомление не найдено",
  "Only the recipient can mark this notification as read":
    "Отметить прочитанным может только получатель",
  "specialist_id is required": "Укажите специалиста",
  "Slot must belong to an active support specialist":
    "Окно можно открыть только активному специалисту",
  "This specialist already has a slot at that time": "У специалиста уже есть окно на это время",
  "Update slot not found": "Окно записи не найдено",
  "You can only change your own slots": "Можно менять только свои окна",
  "Capacity is below the number of bookings": "Вместимость меньше числа уже записанных",
  "Nothing to update": "Нет изменений",
  "Scheduled update not found": "Обновление не найдено",
  "Slot is not active": "Окно закрыто для записи",
  "Slot is in the past": "Это окно уже прошло",
  "Slot is full": "В окне не осталось мест",
  "An open update already exists for this configuration":
    "Для этой установки уже есть незакрытое обновление",
  "Configuration has no current version": "У конфигурации нет текущего релиза",
  "The date can no longer be changed": "Дату уже нельзя изменить",
  "Slot can only be chosen while the update is requested or scheduled":
    "Дату можно выбрать, пока обновление запрошено или назначено",
  "No current version is available to install": "Нет текущего релиза, который можно установить",
  "Status is unchanged": "Статус не изменился",
  "Choose a slot before scheduling": "Сначала выберите окно записи",
  "Version check not found": "Проверка не найдена",
};

const FIELD_LABELS: Record<string, string> = {
  full_name: "Имя",
  email: "Почта",
  password: "Пароль",
  phone: "Телефон",
  role: "Роль",
  client_id: "Организация",
  company_name: "Организация",
  responsible_employee_id: "Ответственный",
  name: "Название",
  description: "Описание",
  version: "Версия",
  released_at: "Дата выпуска",
  is_current: "Текущий релиз",
  notes: "Заметки",
  installed_version_id: "Установленная версия",
  infobase_name: "Информационная база",
  configuration_id: "Конфигурация",
  title: "Заголовок",
  message: "Текст",
  slot_date: "Дата",
  start_time: "Начало",
  end_time: "Окончание",
  capacity: "Вместимость",
  specialist_id: "Специалист",
  client_configuration_id: "Установка",
  slot_id: "Окно",
  comment: "Комментарий",
  status: "Статус",
  is_active: "Активность",
};

export function fieldLabel(name: string): string {
  return FIELD_LABELS[name] ?? name;
}

function isRole(value: string): value is RoleCode {
  return value === "admin" || value === "specialist" || value === "manager" || value === "client";
}

function isStatus(value: string): value is UpdateStatus {
  return (
    value === "requested" ||
    value === "scheduled" ||
    value === "in_progress" ||
    value === "completed" ||
    value === "cancelled"
  );
}

export function translateDetail(detail: string): string {
  const known = DETAILS[detail];
  if (known) return known;
  const transition = detail.match(/^Transition ([a-z_]+) -> ([a-z_]+) is not allowed$/);
  if (transition && transition[1] && transition[2] && isStatus(transition[1]) && isStatus(transition[2])) {
    return `Переход «${statusLabel(transition[1])}» → «${statusLabel(transition[2])}» недопустим`;
  }
  const role = detail.match(/^Role ([a-z_]+) is not configured$/);
  if (role && role[1] && isRole(role[1])) {
    return `Роль «${roleLabel(role[1])}» не настроена в базе. Выполните миграции.`;
  }
  return `Сервер отклонил запрос: ${detail}`;
}

export function translateValidation(message: string): string {
  const msg = message.replace(/^Value error,\s*/i, "");
  if (msg === "Field required") return "Обязательное поле";
  if (msg.includes("end_time must be after start_time")) {
    return "Время окончания должно быть позже начала";
  }
  if (/email/i.test(msg)) return "Укажите корректную почту";
  const min = msg.match(/at least (\d+) character/);
  if (min) return `Минимум ${min[1]} символов`;
  const max = msg.match(/at most (\d+) character/);
  if (max) return `Не больше ${max[1]} символов`;
  const ge = msg.match(/greater than or equal to (\d+)/);
  if (ge) return `Значение не меньше ${ge[1]}`;
  const le = msg.match(/less than or equal to (\d+)/);
  if (le) return `Значение не больше ${le[1]}`;
  if (msg.includes("valid UUID") || msg.includes("valid uuid")) return "Выберите значение из списка";
  if (msg.includes("valid time")) return "Укажите корректное время";
  if (msg.includes("valid date") || msg.includes("valid datetime")) return "Укажите корректную дату";
  if (msg.includes("valid integer") || msg.includes("valid number")) return "Укажите число";
  if (msg.includes("valid boolean")) return "Укажите да или нет";
  return "Проверьте введённое значение";
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly fieldErrors: Record<string, string>;

  constructor(status: number, detail: string, fieldErrors: Record<string, string>) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
  }
}

type ValidationItem = {
  loc?: unknown[];
  msg?: string;
};

export function parseError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return new ApiError(status, translateDetail(detail), {});
    }
    if (Array.isArray(detail)) {
      const fieldErrors: Record<string, string> = {};
      const messages: string[] = [];
      for (const item of detail) {
        if (!item || typeof item !== "object") continue;
        const row = item as ValidationItem;
        const text = translateValidation(row.msg ?? "Проверьте значение");
        const loc = Array.isArray(row.loc) ? row.loc : [];
        const parts = loc.filter(
          (part): part is string =>
            typeof part === "string" && part !== "body" && part !== "query" && part !== "path",
        );
        const key = parts.length ? parts[parts.length - 1] : "";
        if (key) {
          fieldErrors[key] = text;
          messages.push(`${fieldLabel(key)}: ${text}`);
        } else {
          messages.push(text);
        }
      }
      const summary = messages.join(". ") || "Проверьте заполнение формы";
      return new ApiError(status, summary, fieldErrors);
    }
  }
  if (status === 404) return new ApiError(status, "Не найдено", {});
  if (status >= 500) return new ApiError(status, "Сервис временно недоступен", {});
  if (status === 0) return new ApiError(status, "Нет связи с сервером. Проверьте, что API запущен на порту 8000.", {});
  return new ApiError(status, "Не удалось выполнить запрос", {});
}

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof Error && error.message) return new ApiError(0, error.message, {});
  return new ApiError(0, "Не удалось выполнить запрос", {});
}

export function messageOf(error: unknown): string {
  return asApiError(error).detail;
}
