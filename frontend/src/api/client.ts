// The single place that knows the base URL, authentication, CSRF and error mapping (rules/16 ApiClient).

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, details?: unknown) {
    super(code);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

type Listener = () => void;

class ApiClient {
  private csrf: string | null = null;
  private unauthorizedListeners = new Set<Listener>();

  setCsrfToken(token: string | null): void {
    this.csrf = token;
  }

  onUnauthorized(listener: Listener): () => void {
    this.unauthorizedListeners.add(listener);
    return () => this.unauthorizedListeners.delete(listener);
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { "X-Argus-Client": "web", Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET" && this.csrf) headers["X-CSRF-Token"] = this.csrf;

    let response: Response;
    try {
      response = await fetch(`${BASE}${path}`, {
        method,
        headers,
        credentials: "same-origin",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "network_error");
    }

    if (response.status === 204) return undefined as T;
    let payload: { code?: string; details?: unknown } & Record<string, unknown> = {};
    try {
      payload = await response.json();
    } catch {
      /* non-JSON body */
    }
    if (!response.ok) {
      const code = typeof payload.code === "string" ? payload.code : `http_${response.status}`;
      if (response.status === 401 && code === "not_authenticated") {
        this.unauthorizedListeners.forEach((l) => l());
      }
      throw new ApiError(response.status, code, payload.details);
    }
    return payload as T;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }
  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body ?? {});
  }
  put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("PUT", path, body);
  }
}

export const api = new ApiClient();

// ---- typed endpoints ----------------------------------------------------------------------------
export interface SessionInfo {
  authenticated: boolean;
  user: { username: string; full_name: string; role: string; email: string } | null;
  csrf_token: string | null;
  must_change_password: boolean;
  capabilities: string[];
  dev_loginless: boolean;
  dev_banner: string;
  profile: { name: "civil" | "defense"; marking: string };
  password_expires_at: string | null;
}

export interface PasswordSummary {
  min_length: number;
  max_length: number;
  require_upper: boolean;
  require_lower: boolean;
  require_digit: boolean;
  require_special: boolean;
  reject_username: boolean;
  reject_common: boolean;
  history_count: number;
  min_age_hours: number;
  reveal_autohide_seconds: number;
}

export interface PasswordPolicy {
  min_length: number;
  max_length: number;
  require_upper: boolean;
  require_lower: boolean;
  require_digit: boolean;
  require_special: boolean;
  expiration_enabled: boolean;
  expiration_months: number;
  expiry_notice_days: number;
  history_count: number;
  history_applies_to_admin_set: boolean;
  min_age_hours: number;
  reveal_autohide_seconds: number;
  reject_username: boolean;
  reject_common: boolean;
}

export interface PasswordPolicyEnvelope {
  policy: PasswordPolicy;
  limits: Record<string, number>;
}

export interface LockoutPolicy {
  threshold: number;
  window_minutes: number;
  mode: "auto_unlock" | "permanent" | "escalating";
  durations_minutes: number[];
  cycles_before_permanent: number | null;
  unlockers: string[];
  after_unlock: "none" | "require_password_change" | "reset_password";
  revoke_sessions: boolean;
  notify: boolean;
}

export interface LockoutSettings {
  exempt_last_administrator: boolean;
  source_throttle_per_minute: number;
  default: LockoutPolicy;
  roles: Record<string, LockoutPolicy>;
}

export interface LockoutEnvelope {
  settings: LockoutSettings;
  roles: Record<string, number>;
}

export interface SessionPolicy {
  inactivity_minutes: number;
  absolute_hours: number;
}

export interface ProblemDetail {
  code: string;
  fields?: string[];
  scope?: string;
}

export interface LockInfo {
  state: "active" | "locked_temporary" | "locked_permanent";
  manual: boolean;
  until: string | null;
}

export interface UserDto {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  locale: string;
  is_active: boolean;
  is_service: boolean;
  must_change_password: boolean;
  lock: LockInfo;
  password_expires_at: string | null;
  last_login_at: string | null;
  created_at: string;
  email_queued?: boolean;
  email_configured?: boolean;
  after_unlock?: string;
  temporary_password?: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface RoleDto {
  id: number;
  name: string;
  description: string;
  security_level: number;
  is_system: boolean;
  capabilities: string[];
  user_count: number;
  locked: boolean;
}

export interface AuditRow {
  id: number;
  ts: string;
  actor: string;
  actor_role: string;
  channel: string;
  source_ip: string;
  action: string;
  object_type: string;
  object_id: string;
  result: string;
  reason: string;
  changes: Record<string, { old: unknown; new: unknown }>;
  details: Record<string, unknown>;
}

export interface AuditFilters {
  date_from?: string;
  date_to?: string;
  actor?: string;
  action?: string;
  object_type?: string;
  result?: string;
  q?: string;
}

export interface EmailSettings {
  enabled: boolean;
  host: string;
  port: number;
  tls_mode: "none" | "starttls" | "ssl";
  username: string;
  from_address: string;
  from_name: string;
  login_url: string;
  password_set: boolean;
}

export interface TemplateSummary {
  key: string;
  title: string;
  variables: string[];
  sensitive: boolean;
  locales: { locale: string; customized: boolean }[];
}

export interface TemplateDetail {
  key: string;
  locale: string;
  subject: string;
  body_text: string;
  body_html: string;
  version: number;
  customized: boolean;
  variables: string[];
  versions: { version: number; changed_at: string; changed_by: string; subject: string }[];
}

export interface OutboxRow {
  id: number;
  created_at: string;
  template: string;
  to: string;
  subject: string;
  status: string;
  attempts: number;
  error: string;
  sent_at: string | null;
}

export interface AssetDto {
  id: number;
  code: string;
  name: string;
  asset_type: string;
  category: string;
  purdue_level: string;
  zone: string | null;
  location: string;
  x: number | null;
  y: number | null;
  criticality: string;
  status: string;
  exposure: string[];
  vendor: string;
  model: string;
  firmware_version: string;
  ip_address: string;
  mac_address: string;
  protocols: string[];
  notes: string;
  is_demo: boolean;
  last_seen_at: string | null;
  can_ingest: boolean;
  software_count: number;
  software?: { name: string; vendor: string; version: string; cpe: string }[];
  relations?: { outgoing: RelationDto[]; incoming: RelationDto[] };
}

export interface RelationDto {
  id: number;
  relation: string;
  protocol: string;
  note: string;
  source: string;
  target: string;
}

export interface AssetVocabulary {
  types: Record<string, string>;
  levels: string[];
  criticality: string[];
  statuses: string[];
  exposure: string[];
  relations: string[];
  scopes: string[];
  ingest_types: string[];
  transitions: Record<string, string[]>;
}

export interface ZoneDto {
  id: number;
  code: string;
  name: string;
  criticality: string;
  asset_count: number;
}

export interface CredentialDto {
  key_id: string;
  asset: string;
  scopes: string[];
  allowed_networks: string[];
  state: "active" | "retiring" | "revoked" | "expired";
  created_at: string;
  created_by: string;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
  last_used_ip: string;
  secret?: string;
}

export type Classification = "zero_day" | "zero_hour" | "ordinary";

export interface VulnerabilityDto {
  id: number;
  vuln_id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  cvss: number | null;
  epss: number | null;
  kev: boolean;
  fix_status: string;
  is_demo: boolean;
  published_at: string | null;
  first_seen_at: string;
  classification: Classification;
  is_zero_day: boolean;
  is_zero_hour: boolean;
  sources: string[];
  affected_assets?: number;
  description?: string;
  affected?: { vendor: string; product: string; cpe: string; versions: Record<string, unknown> }[];
  references?: string[];
  findings?: FindingDto[];
}

export interface FindingDto {
  id: number;
  status: "open" | "acknowledged" | "mitigated" | "false_positive";
  matched_on: string;
  match_basis: string;
  confidence: "high" | "low";
  first_matched_at: string;
  acknowledged_by: string;
  acknowledged_at: string | null;
  note: string;
  classification: Classification;
  vulnerability: VulnerabilityDto;
  asset: { id: number; code: string; name: string; zone: string | null; criticality: string } | null;
}

export interface IntelSourceDto {
  key: string;
  name: string;
  kind: string;
  enabled: boolean;
  url: string;
  interval_hours: number;
  last_status: string;
  last_error: string;
  last_items: number;
  last_run_at: string | null;
}

export interface IntelPolicyDto {
  zero_hour_hours: number;
  epss_threshold: number;
  notify_min_severity: string;
  notify: boolean;
  offline_only: boolean;
}

export interface IntelOverview {
  open_findings: Record<Classification, number>;
  vulnerabilities: number;
  last_run_at: string | null;
  policy: IntelPolicyDto;
}

export type IncidentType = "hybrid" | "physical" | "cyber";
export type IncidentStatus = "new" | "triaged" | "investigating" | "contained" | "closed";

export interface IncidentDto {
  id: number;
  code: string;
  type: IncidentType;
  severity: "low" | "medium" | "high" | "critical";
  score: number;
  status: IncidentStatus;
  escalated: boolean;
  title: string;
  zone: string | null;
  track_id: string | null;
  primary_asset: string | null;
  link_asset: string | null;
  assigned_to: string;
  created_at: string;
  updated_at: string;
  last_signal_at: string;
  closed_at: string | null;
  blast_count: number;
  evidence?: {
    physical: null | {
      track: { id: string; x: number; y: number; altitude: number | null; zone: string | null; ring: string;
        severity: string; ts: string };
      link: null | { kind: string; exposure: string | null; distance_m: number; radius_m: number; strength: number;
        exposed_asset: string | null; path: string[]; candidates?: { asset: string; exposure: string; distance_m: number }[] };
    };
    cyber: {
      alarms: { summary: string; source: string | null; reported_by: string | null; ts: string | null }[];
      findings: { vuln_id: string; title: string; classification: string; severity: string; fix_status: string }[];
    };
    other_assets?: { asset: string; score: number; signals: number }[];
  };
  blast_radius?: { asset: string; name: string; asset_type: string; hop: number; impact: string; criticality: string;
    via: string[]; consequence: number; zone: string | null }[];
  recommendations?: { code: string; asset?: string; assets?: string[]; zone?: string | null }[];
  transitions?: IncidentStatus[];
  timeline?: { ts: string; kind: string; actor: string; text: string; details: Record<string, unknown> }[];
}

export interface IncidentGraph {
  incident: IncidentDto;
  nodes: {
    id: string; asset_id: number | null; code: string; name: string; asset_type: string; level: string;
    zone: string | null; criticality: string; role: "physical_event" | "entry" | "path" | "compromised" | "at_risk";
    hop: number; impact?: string;
  }[];
  edges: { id: string; source: string; target: string; kind: "relation" | "hybrid"; relation: string }[];
}

export function query(params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
  const text = q.toString();
  return text ? `?${text}` : "";
}

export const endpoints = {
  session: () => api.get<SessionInfo>("/api/v1/auth/session"),
  login: (username: string, password: string) =>
    api.post<SessionInfo>("/api/v1/auth/login", { username, password }),
  logout: () => api.post<void>("/api/v1/auth/logout"),
  changePassword: (current_password: string, new_password: string) =>
    api.post<void>("/api/v1/auth/change-password", { current_password, new_password }),
  passwordSummary: () => api.get<PasswordSummary>("/api/v1/policy/password/summary"),
  generatePassword: () => api.post<{ password: string }>("/api/v1/policy/password/generate"),
  getPasswordPolicy: () => api.get<PasswordPolicyEnvelope>("/api/v1/settings/password-policy"),
  putPasswordPolicy: (policy: PasswordPolicy) =>
    api.put<PasswordPolicyEnvelope>("/api/v1/settings/password-policy", policy),
  getLockout: () => api.get<LockoutEnvelope>("/api/v1/settings/lockout"),
  putLockout: (settings: LockoutSettings) => api.put<LockoutEnvelope>("/api/v1/settings/lockout", settings),
  getSessionPolicy: () => api.get<SessionPolicy>("/api/v1/settings/session"),
  putSessionPolicy: (policy: SessionPolicy) => api.put<SessionPolicy>("/api/v1/settings/session", policy),

  // users
  listUsers: (p: { search?: string; role?: string; page?: number; page_size?: number }) =>
    api.get<Page<UserDto>>(`/api/v1/users${query(p)}`),
  assignableRoles: () => api.get<{ id: number; name: string; security_level: number }[]>("/api/v1/users/roles"),
  createUser: (body: {
    username: string; email: string; full_name: string; role: string; locale: string; password: string;
    send_email: boolean;
  }) => api.post<UserDto>("/api/v1/users", body),
  updateUser: (id: number, body: Partial<Pick<UserDto, "email" | "full_name" | "role" | "locale" | "is_active">>) =>
    api.put<UserDto>(`/api/v1/users/${id}`, body),
  deleteUser: (id: number) => api.request<void>("DELETE", `/api/v1/users/${id}`),
  lockUser: (id: number, reason: string) => api.post<UserDto>(`/api/v1/users/${id}/lock`, { reason }),
  unlockUser: (id: number) => api.post<UserDto>(`/api/v1/users/${id}/unlock`),
  resetPassword: (id: number, password: string) =>
    api.post<UserDto>(`/api/v1/users/${id}/reset-password`, { password }),

  // roles
  listRoles: () => api.get<{ roles: RoleDto[]; capabilities: string[] }>("/api/v1/roles"),
  createRole: (body: { name: string; description: string; security_level: number; capabilities: string[] }) =>
    api.post<RoleDto>("/api/v1/roles", body),
  updateRole: (id: number, body: { description?: string; capabilities?: string[] }) =>
    api.put<RoleDto>(`/api/v1/roles/${id}`, body),
  deleteRole: (id: number) => api.request<void>("DELETE", `/api/v1/roles/${id}`),

  // audit
  listAudit: (f: AuditFilters & { page?: number; page_size?: number }) =>
    api.get<Page<AuditRow>>(`/api/v1/audit${query({ ...f })}`),
  auditExportUrl: (f: AuditFilters) => `${BASE}/api/v1/audit/export${query({ ...f })}`,
  verifyAudit: () => api.get<{ intact: boolean }>("/api/v1/audit/verify"),

  // e-mail
  getEmail: () => api.get<EmailSettings>("/api/v1/settings/email"),
  putEmail: (body: Partial<EmailSettings> & { password?: string; clear_password?: boolean }) =>
    api.put<EmailSettings>("/api/v1/settings/email", body),
  testEmail: (to: string) =>
    api.post<{ status: string; error: string; sent: number }>("/api/v1/settings/email/test", to ? { to } : {}),
  outbox: () => api.get<OutboxRow[]>("/api/v1/settings/email/outbox"),
  templates: () => api.get<TemplateSummary[]>("/api/v1/settings/email/templates"),
  template: (key: string, locale: string) =>
    api.get<TemplateDetail>(`/api/v1/settings/email/templates/${key}${query({ locale })}`),
  saveTemplate: (key: string, locale: string, body: { subject: string; body_text: string; body_html: string }) =>
    api.put<{ version: number }>(`/api/v1/settings/email/templates/${key}${query({ locale })}`, body),
  resetTemplate: (key: string, locale: string) =>
    api.request<void>("DELETE", `/api/v1/settings/email/templates/${key}${query({ locale })}`),
  previewTemplate: (key: string, locale: string, body: { subject: string; body_text: string; body_html: string }) =>
    api.post<{ subject: string; text: string; html: string }>(
      `/api/v1/settings/email/templates/${key}/preview${query({ locale })}`, body),

  // assets
  vocabulary: () => api.get<AssetVocabulary>("/api/v1/assets/vocabulary"),
  zones: () => api.get<ZoneDto[]>("/api/v1/zones"),
  listAssets: (p: Record<string, string | number | undefined>) => api.get<Page<AssetDto>>(`/api/v1/assets${query(p)}`),
  getAsset: (id: number) => api.get<AssetDto>(`/api/v1/assets/${id}`),
  createAsset: (body: Record<string, unknown>) => api.post<AssetDto>("/api/v1/assets", body),
  updateAsset: (id: number, body: Record<string, unknown>) => api.put<AssetDto>(`/api/v1/assets/${id}`, body),
  deleteAsset: (id: number) => api.request<void>("DELETE", `/api/v1/assets/${id}`),
  setSoftware: (id: number, items: { name: string; vendor: string; version: string; cpe: string }[]) =>
    api.put<AssetDto>(`/api/v1/assets/${id}/software`, { items }),
  addRelation: (id: number, body: { target: string; relation: string; protocol: string; note: string; direction: string }) =>
    api.post<{ outgoing: RelationDto[]; incoming: RelationDto[] }>(`/api/v1/assets/${id}/relations`, body),
  removeRelation: (id: number, relationId: number) =>
    api.request<{ outgoing: RelationDto[]; incoming: RelationDto[] }>(
      "DELETE", `/api/v1/assets/${id}/relations/${relationId}`),
  credentials: (id: number) => api.get<CredentialDto[]>(`/api/v1/assets/${id}/credentials`),
  createCredential: (id: number, body: { scopes: string[]; allowed_networks: string[]; valid_days: number }) =>
    api.post<CredentialDto>(`/api/v1/assets/${id}/credentials`, body),
  rotateCredential: (keyId: string, grace_minutes: number) =>
    api.post<CredentialDto>(`/api/v1/credentials/${keyId}/rotate`, { grace_minutes }),
  revokeCredential: (keyId: string) => api.post<CredentialDto>(`/api/v1/credentials/${keyId}/revoke`),

  // threat intelligence
  intelOverview: () => api.get<IntelOverview>("/api/v1/intel/overview"),
  findings: (p: Record<string, string | number | undefined>) => api.get<Page<FindingDto>>(`/api/v1/intel/findings${query(p)}`),
  updateFinding: (id: number, status: string, note: string) =>
    api.put<FindingDto>(`/api/v1/intel/findings/${id}`, { status, note }),
  vulnerabilities: (p: Record<string, string | number | undefined>) =>
    api.get<Page<VulnerabilityDto>>(`/api/v1/intel/vulnerabilities${query(p)}`),
  vulnerability: (id: string) => api.get<VulnerabilityDto>(`/api/v1/intel/vulnerabilities/${id}`),
  intelSources: () => api.get<IntelSourceDto[]>("/api/v1/intel/sources"),
  updateIntelSource: (key: string, body: { enabled?: boolean; url?: string; interval_hours?: number }) =>
    api.put<IntelSourceDto>(`/api/v1/intel/sources/${key}`, body),
  runIntelSource: (key: string) => api.post<IntelSourceDto & { report: { created: number; updated: number } | null }>(
    `/api/v1/intel/sources/${key}/run`),
  importIntel: (format: string, payload: unknown) =>
    api.post<{ created: number; updated: number; skipped: number; new_findings: number; notified: number }>(
      "/api/v1/intel/import", { format, payload }),
  intelPolicy: () => api.get<IntelPolicyDto>("/api/v1/intel/policy"),
  putIntelPolicy: (p: IntelPolicyDto) => api.put<IntelPolicyDto>("/api/v1/intel/policy", p),
  trustedKeys: () => api.get<{ key_id: string; public_key: string; label: string }[]>("/api/v1/intel/trusted-keys"),
  putTrustedKeys: (keys: { key_id: string; public_key: string; label: string }[]) =>
    api.put<{ key_id: string; public_key: string; label: string }[]>("/api/v1/intel/trusted-keys", { keys }),

  // incidents
  incidents: (p: Record<string, string | number | boolean | undefined>) =>
    api.get<Page<IncidentDto>>(`/api/v1/incidents${query(p as Record<string, string | number | undefined>)}`),
  incident: (id: number) => api.get<IncidentDto>(`/api/v1/incidents/${id}`),
  incidentGraph: (id: number) => api.get<IncidentGraph>(`/api/v1/incidents/${id}/graph`),
  setIncidentStatus: (id: number, status: string, note: string) =>
    api.post<IncidentDto>(`/api/v1/incidents/${id}/status`, { status, note }),
  escalateIncident: (id: number, text: string) => api.post<IncidentDto>(`/api/v1/incidents/${id}/escalate`, { text }),
  noteIncident: (id: number, text: string) => api.post<IncidentDto>(`/api/v1/incidents/${id}/notes`, { text }),
};
