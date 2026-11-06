export type RoleCode = "admin" | "specialist" | "manager" | "client";

export type UpdateStatus =
  | "requested"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "cancelled";

export type NotificationType =
  | "update_available"
  | "update_scheduled"
  | "update_completed"
  | "update_cancelled";

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type Health = {
  status: string;
  app: string;
  database: string;
};

export type RoleRead = {
  id: string;
  code: RoleCode;
  name: string;
};

export type UserRead = {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  is_active: boolean;
  role: RoleCode;
  client_id: string | null;
  client_name: string | null;
  created_at: string;
  updated_at: string;
};

export type UserCreate = {
  full_name: string;
  email: string;
  password: string;
  phone?: string | null;
  role: RoleCode;
  client_id?: string | null;
};

export type UserUpdate = {
  full_name?: string | null;
  phone?: string | null;
  password?: string | null;
  is_active?: boolean | null;
  role?: RoleCode | null;
  client_id?: string | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: RoleCode;
  user: UserRead;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type ClientRead = {
  id: string;
  company_name: string;
  phone: string;
  email: string;
  responsible_employee_id: string | null;
  responsible_employee_name: string | null;
  created_at: string;
  updated_at: string;
};

export type ClientCreate = {
  company_name: string;
  phone: string;
  email: string;
  responsible_employee_id?: string | null;
};

export type ClientUpdate = {
  company_name?: string | null;
  phone?: string | null;
  email?: string | null;
  responsible_employee_id?: string | null;
};

export type VersionRead = {
  id: string;
  configuration_id: string;
  version: string;
  released_at: string | null;
  is_current: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ConfigurationRead = {
  id: string;
  name: string;
  description: string | null;
  current_version: string | null;
  created_at: string;
  updated_at: string;
};

export type ConfigurationDetail = ConfigurationRead & {
  versions: VersionRead[];
};

export type ConfigurationCreate = {
  name: string;
  description?: string | null;
};

export type ConfigurationUpdate = {
  name?: string | null;
  description?: string | null;
};

export type VersionCreate = {
  version: string;
  released_at?: string | null;
  is_current?: boolean;
  notes?: string | null;
};

export type VersionUpdate = {
  released_at?: string | null;
  is_current?: boolean | null;
  notes?: string | null;
};

export type ClientConfigurationRead = {
  id: string;
  client_id: string;
  company_name: string;
  configuration_id: string;
  configuration_name: string;
  installed_version_id: string;
  installed_version: string;
  current_version_id: string | null;
  current_version: string | null;
  is_outdated: boolean | null;
  infobase_name: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ClientConfigurationCreate = {
  configuration_id: string;
  installed_version_id: string;
  infobase_name?: string | null;
};

export type ClientConfigurationUpdate = {
  installed_version_id?: string | null;
  infobase_name?: string | null;
};

export type VersionCheckRead = {
  id: string;
  client_configuration_id: string;
  client_id: string;
  company_name: string;
  configuration_name: string;
  installed_version_id: string;
  installed_version: string;
  actual_version_id: string;
  actual_version: string;
  is_outdated: boolean;
  checked_at: string;
  checked_by_id: string;
  checked_by_name: string;
};

export type RunChecksRequest = {
  client_id?: string | null;
  client_configuration_id?: string | null;
};

export type SkippedCheck = {
  client_configuration_id: string;
  reason: string;
};

export type RunChecksResponse = {
  created: VersionCheckRead[];
  skipped: SkippedCheck[];
};

export type OutdatedConfiguration = {
  client_configuration_id: string;
  configuration_id: string;
  configuration_name: string;
  infobase_name: string | null;
  installed_version_id: string;
  installed_version: string;
  current_version_id: string;
  current_version: string;
};

export type OutdatedClient = {
  client_id: string;
  company_name: string;
  email: string;
  phone: string;
  configurations: OutdatedConfiguration[];
};

export type OutdatedReport = {
  total_clients: number;
  total_configurations: number;
  clients: OutdatedClient[];
};

export type NotificationRead = {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  client_id: string;
  company_name: string;
  client_configuration_id: string | null;
  configuration_name: string | null;
  scheduled_update_id: string | null;
  recipient_id: string;
  created_by_id: string | null;
};

export type NotificationList = {
  items: NotificationRead[];
  total: number;
  unread: number;
  limit: number;
  offset: number;
};

export type NotificationCreate = {
  client_id: string;
  client_configuration_id?: string | null;
  title?: string | null;
  message?: string | null;
};

export type SlotRead = {
  id: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
  booked: number;
  remaining: number;
  is_active: boolean;
  specialist_id: string;
  specialist_name: string;
};

export type SlotCreate = {
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity?: number;
  specialist_id?: string | null;
};

export type SlotUpdate = {
  is_active?: boolean | null;
  capacity?: number | null;
};

export type AvailableDate = {
  slot_date: string;
  open_slots: number;
  remaining_capacity: number;
};

export type StatusEventRead = {
  id: string;
  old_status: UpdateStatus | null;
  new_status: UpdateStatus;
  comment: string | null;
  changed_at: string;
  changed_by_id: string;
  changed_by_name: string;
};

export type ScheduledUpdateRead = {
  id: string;
  status: UpdateStatus;
  comment: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  client_id: string;
  company_name: string;
  client_configuration_id: string;
  configuration_name: string;
  infobase_name: string | null;
  source_version_id: string | null;
  source_version: string | null;
  target_version_id: string | null;
  target_version: string | null;
  slot_id: string | null;
  slot_date: string | null;
  slot_start: string | null;
  slot_end: string | null;
  requested_by_id: string;
  requested_by_name: string;
  assigned_specialist_id: string | null;
  assigned_specialist_name: string | null;
};

export type ScheduledUpdateDetail = ScheduledUpdateRead & {
  status_history: StatusEventRead[];
};

export type ScheduledUpdateCreate = {
  client_configuration_id: string;
  slot_id?: string | null;
  comment?: string | null;
};

export type ScheduledUpdatePatch = {
  slot_id?: string | null;
  comment?: string | null;
};

export type StatusChange = {
  status: UpdateStatus;
  comment?: string | null;
};

export type UpdatedConfigurationReport = {
  scheduled_update_id: string;
  client_configuration_id: string;
  configuration_name: string;
  source_version: string | null;
  target_version: string | null;
  completed_at: string | null;
  assigned_specialist_name: string | null;
};

export type UpdatedClientReport = {
  client_id: string;
  company_name: string;
  updates: UpdatedConfigurationReport[];
};

export type UpdatedClientsReport = {
  date_from: string | null;
  date_to: string | null;
  total_clients: number;
  total_updates: number;
  clients: UpdatedClientReport[];
};

export type UpdateBrief = {
  id: string;
  status: UpdateStatus;
  client_id: string;
  company_name: string;
  configuration_name: string;
  slot_date: string | null;
  completed_at: string | null;
  created_at: string;
};

export type UpdatesReport = {
  date_from: string | null;
  date_to: string | null;
  planned_count: number;
  completed_count: number;
  cancelled_count: number;
  by_status: Record<string, number>;
  planned: UpdateBrief[];
  completed: UpdateBrief[];
};

export type PageQuery = {
  limit?: number;
  offset?: number;
};
