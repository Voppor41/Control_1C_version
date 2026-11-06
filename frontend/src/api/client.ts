import { clearSession, readToken } from "../auth/storage";
import { ApiError, parseError } from "./errors";
import type {
  AvailableDate,
  ClientConfigurationCreate,
  ClientConfigurationRead,
  ClientConfigurationUpdate,
  ClientCreate,
  ClientRead,
  ClientUpdate,
  ConfigurationCreate,
  ConfigurationDetail,
  ConfigurationRead,
  ConfigurationUpdate,
  Health,
  LoginRequest,
  NotificationCreate,
  NotificationList,
  NotificationRead,
  NotificationType,
  OutdatedReport,
  Page,
  RoleCode,
  RoleRead,
  RunChecksRequest,
  RunChecksResponse,
  ScheduledUpdateCreate,
  ScheduledUpdateDetail,
  ScheduledUpdatePatch,
  ScheduledUpdateRead,
  SlotCreate,
  SlotRead,
  SlotUpdate,
  StatusChange,
  TokenResponse,
  UpdatedClientsReport,
  UpdateStatus,
  UpdatesReport,
  UserCreate,
  UserRead,
  UserUpdate,
  VersionCheckRead,
  VersionCreate,
  VersionRead,
  VersionUpdate,
} from "./types";

type QueryValue = string | number | boolean | null | undefined;

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
};

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function withQuery(path: string, query: Record<string, QueryValue> = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

function readJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers();
  if (options.auth !== false) {
    const token = readToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  let body: string | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером. Проверьте, что API запущен на порту 8000.", {});
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const payload = text ? readJson(text) : null;

  if (!response.ok) {
    const error = parseError(response.status, payload);
    if (response.status === 401 && options.auth !== false) {
      clearSession();
      onUnauthorized();
    }
    throw error;
  }
  return payload as T;
}

export const api = {
  health: () => request<Health>("/health", { auth: false }),
  login: (body: LoginRequest) =>
    request<TokenResponse>("/api/auth/login", { method: "POST", body, auth: false }),
  me: () => request<UserRead>("/api/auth/me"),

  listRoles: () => request<RoleRead[]>("/api/roles"),
  listUsers: (query: { q?: string; role?: RoleCode; is_active?: boolean; limit?: number; offset?: number } = {}) =>
    request<Page<UserRead>>(withQuery("/api/users", query)),
  createUser: (body: UserCreate) => request<UserRead>("/api/users", { method: "POST", body }),
  updateUser: (id: string, body: UserUpdate) =>
    request<UserRead>(`/api/users/${id}`, { method: "PATCH", body }),

  listClients: (query: { q?: string; limit?: number; offset?: number } = {}) =>
    request<Page<ClientRead>>(withQuery("/api/clients", query)),
  getClient: (id: string) => request<ClientRead>(`/api/clients/${id}`),
  createClient: (body: ClientCreate) => request<ClientRead>("/api/clients", { method: "POST", body }),
  updateClient: (id: string, body: ClientUpdate) =>
    request<ClientRead>(`/api/clients/${id}`, { method: "PATCH", body }),
  deleteClient: (id: string) => request<void>(`/api/clients/${id}`, { method: "DELETE" }),

  listConfigurations: (query: { q?: string; limit?: number; offset?: number } = {}) =>
    request<Page<ConfigurationRead>>(withQuery("/api/configurations", query)),
  getConfiguration: (id: string) => request<ConfigurationDetail>(`/api/configurations/${id}`),
  createConfiguration: (body: ConfigurationCreate) =>
    request<ConfigurationRead>("/api/configurations", { method: "POST", body }),
  updateConfiguration: (id: string, body: ConfigurationUpdate) =>
    request<ConfigurationDetail>(`/api/configurations/${id}`, { method: "PATCH", body }),
  deleteConfiguration: (id: string) => request<void>(`/api/configurations/${id}`, { method: "DELETE" }),
  createVersion: (id: string, body: VersionCreate) =>
    request<VersionRead>(`/api/configurations/${id}/versions`, { method: "POST", body }),
  updateVersion: (configurationId: string, versionId: string, body: VersionUpdate) =>
    request<VersionRead>(`/api/configurations/${configurationId}/versions/${versionId}`, {
      method: "PATCH",
      body,
    }),
  deleteVersion: (configurationId: string, versionId: string) =>
    request<void>(`/api/configurations/${configurationId}/versions/${versionId}`, { method: "DELETE" }),

  listInstallations: (
    query: {
      q?: string;
      client_id?: string;
      configuration_id?: string;
      outdated?: boolean;
      limit?: number;
      offset?: number;
    } = {},
  ) => request<Page<ClientConfigurationRead>>(withQuery("/api/client-configurations", query)),
  listClientInstallations: (
    clientId: string,
    query: { q?: string; outdated?: boolean; limit?: number; offset?: number } = {},
  ) => request<Page<ClientConfigurationRead>>(withQuery(`/api/clients/${clientId}/configurations`, query)),
  createInstallation: (clientId: string, body: ClientConfigurationCreate) =>
    request<ClientConfigurationRead>(`/api/clients/${clientId}/configurations`, { method: "POST", body }),
  updateInstallation: (id: string, body: ClientConfigurationUpdate) =>
    request<ClientConfigurationRead>(`/api/client-configurations/${id}`, { method: "PATCH", body }),
  deleteInstallation: (id: string) =>
    request<void>(`/api/client-configurations/${id}`, { method: "DELETE" }),

  runChecks: (body: RunChecksRequest) =>
    request<RunChecksResponse>("/api/version-checks/run", { method: "POST", body }),
  outdated: (query: { q?: string; client_id?: string } = {}) =>
    request<OutdatedReport>(withQuery("/api/version-checks/outdated", query)),
  listChecks: (
    query: {
      client_id?: string;
      client_configuration_id?: string;
      is_outdated?: boolean;
      date_from?: string;
      date_to?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => request<Page<VersionCheckRead>>(withQuery("/api/version-checks", query)),

  listNotifications: (
    query: {
      is_read?: boolean;
      type?: NotificationType;
      client_id?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => request<NotificationList>(withQuery("/api/notifications", query)),
  createNotification: (body: NotificationCreate) =>
    request<NotificationRead[]>("/api/notifications", { method: "POST", body }),
  markNotificationRead: (id: string) =>
    request<NotificationRead>(`/api/notifications/${id}/read`, { method: "POST" }),

  listSlots: (
    query: {
      available_only?: boolean;
      date_from?: string;
      date_to?: string;
      specialist_id?: string;
      is_active?: boolean;
      limit?: number;
      offset?: number;
    } = {},
  ) => request<Page<SlotRead>>(withQuery("/api/update-slots", query)),
  availableDates: (query: { date_from?: string; date_to?: string } = {}) =>
    request<AvailableDate[]>(withQuery("/api/update-slots/dates", query)),
  createSlot: (body: SlotCreate) => request<SlotRead>("/api/update-slots", { method: "POST", body }),
  updateSlot: (id: string, body: SlotUpdate) =>
    request<SlotRead>(`/api/update-slots/${id}`, { method: "PATCH", body }),

  listUpdates: (
    query: {
      status?: UpdateStatus;
      client_id?: string;
      date_from?: string;
      date_to?: string;
      assigned_specialist_id?: string;
      q?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => request<Page<ScheduledUpdateRead>>(withQuery("/api/scheduled-updates", query)),
  getUpdate: (id: string) => request<ScheduledUpdateDetail>(`/api/scheduled-updates/${id}`),
  createUpdate: (body: ScheduledUpdateCreate) =>
    request<ScheduledUpdateDetail>("/api/scheduled-updates", { method: "POST", body }),
  patchUpdate: (id: string, body: ScheduledUpdatePatch) =>
    request<ScheduledUpdateDetail>(`/api/scheduled-updates/${id}`, { method: "PATCH", body }),
  changeUpdateStatus: (id: string, body: StatusChange) =>
    request<ScheduledUpdateDetail>(`/api/scheduled-updates/${id}/status`, { method: "PATCH", body }),

  reportUpdatedClients: (query: { date_from?: string; date_to?: string; q?: string } = {}) =>
    request<UpdatedClientsReport>(withQuery("/api/reports/updated-clients", query)),
  reportUpdates: (query: { date_from?: string; date_to?: string; q?: string } = {}) =>
    request<UpdatesReport>(withQuery("/api/reports/updates", query)),
  reportOutdated: (query: { q?: string; client_id?: string } = {}) =>
    request<OutdatedReport>(withQuery("/api/reports/outdated-clients", query)),
};
