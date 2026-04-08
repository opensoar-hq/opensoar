const BASE = '/api/v1'

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('opensoar_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function postJSON<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function deleteJSON(path: string): Promise<{ detail: string }> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function patchJSON<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function putJSON<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// Types

export interface Alert {
  id: string
  source: string
  source_id: string | null
  title: string
  description: string | null
  severity: string
  status: string
  source_ip: string | null
  dest_ip: string | null
  hostname: string | null
  rule_name: string | null
  iocs: Record<string, string[]> | null
  tags: string[] | null
  assigned_to: string | null
  assigned_username: string | null
  duplicate_count: number
  partner: string | null
  determination: string
  created_at: string
  updated_at: string
}

export interface AlertDetail extends Alert {
  raw_payload: Record<string, unknown>
  normalized: Record<string, unknown>
  resolved_at: string | null
  resolve_reason: string | null
}

export interface AlertList {
  alerts: Alert[]
  total: number
}

export interface Playbook {
  id: string
  name: string
  description: string | null
  partner: string | null
  execution_order: number
  module_path: string
  function_name: string
  trigger_type: string | null
  trigger_config: Record<string, unknown>
  enabled: boolean
  version: number
  created_at: string
}

export interface ActionResult {
  id: string
  action_name: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  error: string | null
  attempt: number
}

export interface PlaybookRun {
  id: string
  playbook_id: string
  alert_id: string | null
  sequence_id: string | null
  sequence_position: number | null
  sequence_total: number | null
  status: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  result: Record<string, unknown> | null
  action_results: ActionResult[]
  created_at: string
}

export interface PlaybookRunList {
  runs: PlaybookRun[]
  total: number
}

export interface DashboardStats {
  alerts_by_severity: Record<string, number>
  alerts_by_status: Record<string, number>
  alerts_by_partner: Record<string, number>
  alerts_by_determination: Record<string, number>
  open_by_partner: Record<string, number>
  mttr_by_partner: Record<string, number | null>
  total_alerts: number
  total_runs: number
  open_alerts: number
  alerts_today: number
  active_runs: number
  unassigned_count: number
  mttr_seconds: number | null
  priority_queue: Alert[]
  my_alerts: Alert[]
  recent_alerts: Alert[]
  recent_runs: PlaybookRun[]
}

export interface Analyst {
  id: string
  username: string
  display_name: string
  email: string | null
  is_active: boolean
  has_local_password: boolean
  role: string
  created_at: string
}

export interface AnalystRole {
  id: string
  label: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  analyst: Analyst
}

export interface AuthProviderCapability {
  id: string
  name: string
  type: string
  login_url: string | null
}

export interface AuthCapabilities {
  local_login_enabled: boolean
  local_registration_enabled: boolean
  providers: AuthProviderCapability[]
}

export interface Activity {
  id: string
  alert_id: string | null
  incident_id: string | null
  analyst_id: string | null
  analyst_username: string | null
  action: string
  detail: string | null
  metadata_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ActivityList {
  activities: Activity[]
  total: number
}

export interface AvailableAction {
  name: string
  integration: string
  description: string | null
  ioc_types: string[]
}

export interface BulkOperationResult {
  updated: number
  failed: number
  errors: string[]
}

export interface Integration {
  id: string
  integration_type: string
  name: string
  partner: string | null
  enabled: boolean
  health_status: string | null
  last_health_check: string | null
  created_at: string
}

export interface ApiKeyInfo {
  id: string
  name: string
  prefix: string
  is_active: boolean
  created_at: string
  key?: string
}

export interface ApiKeyScopeInfo {
  api_key_id: string
  scopes: string[]
  tenant_id: string | null
}

export interface Incident2 {
  id: string
  title: string
  description: string | null
  severity: string
  status: string
  assigned_to: string | null
  assigned_username: string | null
  tags: string[] | null
  alert_count: number
  closed_at: string | null
  created_at: string
  updated_at: string
}

export interface TenantInfo {
  id: string
  name: string
  slug: string
  legacy_partner_key: string | null
  is_active: boolean
  config: Record<string, unknown>
  alert_count: number
  analyst_count: number
}

export interface GlobalResourceSummary {
  id: string
  name: string
  resource_type: string
  created_at: string
}

export interface GlobalResourceInventory {
  integrations: GlobalResourceSummary[]
  playbooks: GlobalResourceSummary[]
}

export interface SSOProviderInfo {
  id: string
  provider_type: string
  name: string
  issuer: string
  client_id: string
  authorize_url: string
  token_url: string
  userinfo_url: string | null
  jwks_uri: string | null
  scope: string
  enabled: boolean
  extra_config: Record<string, unknown>
}

export interface ReportScheduleInfo {
  id: string
  report_type: string
  format: string
  cadence: string
  destination_email: string | null
  tenant_id: string | null
  is_active: boolean
  config: Record<string, unknown>
  last_run_at: string | null
  last_run_status: string | null
  last_run_detail: string | null
}

export interface DataRetentionPolicyInfo {
  id: string
  audit_log_retention_days: number | null
  report_run_retention_days: number | null
  auto_apply_enabled: boolean
  last_enforced_at: string | null
  last_enforcement_summary: Record<string, unknown> | null
  notes: string | null
}

export interface DataRetentionEnforcementInfo {
  audit_log_entries_deleted: number
  report_runs_cleared: number
  enforced_at: string
}

export interface Observable {
  id: string
  type: string
  value: string
  source: string | null
  enrichment_status: string
  enrichments: Record<string, unknown>[] | null
  tags: string[] | null
  created_at: string
}

export interface IncidentSuggestion {
  source_ip: string
  alert_count: number
  alerts: Alert[]
}

export interface WebhookResponse {
  alert_id: string
  title: string
  severity: string
  playbooks_triggered: string[]
  message: string
}

export interface ActionExecuteResponse {
  action_name: string
  ioc_value: string
  status: string
  result: Record<string, unknown> | null
  error: string | null
}

// API

export const api = {
  auth: {
    register: (data: { username: string; display_name: string; password: string; email?: string }) =>
      postJSON<TokenResponse>('/auth/register', data),
    login: (data: { username: string; password: string }) =>
      postJSON<TokenResponse>('/auth/login', data),
    me: () => fetchJSON<Analyst>('/auth/me'),
    capabilities: () => fetchJSON<AuthCapabilities>('/auth/capabilities'),
    roles: () => fetchJSON<AnalystRole[]>('/auth/roles'),
    changePassword: (data: { current_password: string; new_password: string }) =>
      postJSON<{ detail: string }>('/auth/change-password', data),
  },
  webhooks: {
    createAlert: (payload: Record<string, unknown>) =>
      postJSON<WebhookResponse>('/webhooks/alerts', payload),
  },
  alerts: {
    list: (params?: { status?: string; severity?: string; source?: string; partner?: string; tenant_id?: string; determination?: string; search?: string; limit?: number; offset?: number }) => {
      const sp = new URLSearchParams()
      if (params?.status) sp.set('status', params.status)
      if (params?.severity) sp.set('severity', params.severity)
      if (params?.source) sp.set('source', params.source)
      if (params?.partner) sp.set('partner', params.partner)
      if (params?.tenant_id) sp.set('tenant_id', params.tenant_id)
      if (params?.determination) sp.set('determination', params.determination)
      if (params?.limit) sp.set('limit', String(params.limit))
      if (params?.offset) sp.set('offset', String(params.offset))
      const qs = sp.toString()
      return fetchJSON<AlertList>(`/alerts${qs ? `?${qs}` : ''}`)
    },
    get: (id: string) => fetchJSON<AlertDetail>(`/alerts/${id}`),
    update: (id: string, data: { status?: string; severity?: string; resolve_reason?: string; determination?: string; partner?: string; assigned_to?: string }) =>
      patchJSON<Alert>(`/alerts/${id}`, data),
    claim: (id: string) => postJSON<Alert>(`/alerts/${id}/claim`, {}),
    getRuns: (alertId: string) => fetchJSON<PlaybookRunList>(`/alerts/${alertId}/runs`),
    getIncidents: (alertId: string) => fetchJSON<Incident2[]>(`/alerts/${alertId}/incidents`),
    attachIncident: (
      alertId: string,
      data: {
        incident_id?: string
        title?: string
        description?: string
        severity?: string
        tags?: string[]
      },
    ) => postJSON<Incident2>(`/alerts/${alertId}/incidents`, data),
    getActivities: (alertId: string) => fetchJSON<ActivityList>(`/alerts/${alertId}/activities`),
    addComment: (alertId: string, text: string) =>
      postJSON<Activity>(`/alerts/${alertId}/comments`, { text }),
    editComment: (alertId: string, commentId: string, text: string) =>
      patchJSON<Activity>(`/alerts/${alertId}/comments/${commentId}`, { text }),
    bulk: (data: { alert_ids: string[]; action: string; resolve_reason?: string; determination?: string; severity?: string }) =>
      postJSON<BulkOperationResult>('/alerts/bulk', data),
  },
  playbooks: {
    list: (tenantId?: string) => fetchJSON<Playbook[]>(`/playbooks${tenantId ? `?tenant_id=${tenantId}` : ''}`),
    get: (id: string) => fetchJSON<Playbook>(`/playbooks/${id}`),
    update: (id: string, data: { enabled?: boolean; partner?: string | null }) =>
      patchJSON<Playbook>(`/playbooks/${id}`, data),
    run: (id: string, data?: { alert_id?: string }) =>
      postJSON<{ message: string; celery_task_id: string }>(`/playbooks/${id}/run`, data || {}),
  },
  runs: {
    list: (params?: { status?: string; playbook_id?: string; tenant_id?: string; limit?: number; offset?: number }) => {
      const sp = new URLSearchParams()
      if (params?.status) sp.set('status', params.status)
      if (params?.playbook_id) sp.set('playbook_id', params.playbook_id)
      if (params?.tenant_id) sp.set('tenant_id', params.tenant_id)
      if (params?.limit) sp.set('limit', String(params.limit))
      if (params?.offset) sp.set('offset', String(params.offset))
      const qs = sp.toString()
      return fetchJSON<PlaybookRunList>(`/runs${qs ? `?${qs}` : ''}`)
    },
    get: (id: string) => fetchJSON<PlaybookRun>(`/runs/${id}`),
  },
  actions: {
    available: (iocType?: string) => {
      const qs = iocType ? `?ioc_type=${iocType}` : ''
      return fetchJSON<AvailableAction[]>(`/actions${qs}`)
    },
    execute: (data: { action_name: string; ioc_type: string; ioc_value: string; alert_id?: string }) =>
      postJSON<ActionExecuteResponse>('/actions/execute', data),
  },
  integrations: {
    list: () => fetchJSON<Integration[]>('/integrations'),
    types: () => fetchJSON<{ type: string; display_name: string; description: string }[]>('/integrations/types'),
    create: (data: { integration_type: string; name: string; partner?: string | null; config: Record<string, unknown>; enabled?: boolean }) =>
      postJSON<Integration>('/integrations', data),
    update: (id: string, data: { name?: string; partner?: string | null; config?: Record<string, unknown>; enabled?: boolean }) =>
      patchJSON<Integration>(`/integrations/${id}`, data),
    delete: (id: string) => deleteJSON(`/integrations/${id}`),
    healthCheck: (id: string) => postJSON<{ healthy: boolean; message: string; details: Record<string, unknown> | null }>(`/integrations/${id}/health`, {}),
  },
  apiKeys: {
    list: () => fetchJSON<ApiKeyInfo[]>('/api-keys'),
    create: (data: { name: string }) => postJSON<ApiKeyInfo>('/api-keys', data),
    revoke: (id: string) => deleteJSON(`/api-keys/${id}`),
  },
  apiKeyScopes: {
    get: (id: string) => fetchJSON<ApiKeyScopeInfo>(`/api-key-scopes/${id}`),
    update: (id: string, data: { scopes: string[]; tenant_id?: string | null }) =>
      putJSON<ApiKeyScopeInfo>(`/api-key-scopes/${id}`, data as Record<string, unknown>),
  },
  analysts: {
    list: () => fetchJSON<Analyst[]>('/auth/analysts'),
    create: (data: { username: string; display_name: string; password: string; email?: string; role?: string }) =>
      postJSON<Analyst>('/auth/analysts', data),
    update: (id: string, data: { display_name?: string; email?: string; is_active?: boolean; role?: string }) =>
      patchJSON<Analyst>(`/auth/analysts/${id}`, data),
    resetPassword: (id: string, data: { new_password: string }) =>
      postJSON<{ detail: string }>(`/auth/analysts/${id}/reset-password`, data),
  },
  incidents: {
    list: (params?: { status?: string; severity?: string; tenant_id?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams()
      if (params?.status) qs.set('status', params.status)
      if (params?.severity) qs.set('severity', params.severity)
      if (params?.tenant_id) qs.set('tenant_id', params.tenant_id)
      if (params?.limit) qs.set('limit', String(params.limit))
      if (params?.offset) qs.set('offset', String(params.offset))
      const q = qs.toString()
      return fetchJSON<{ incidents: Incident2[]; total: number }>(`/incidents${q ? `?${q}` : ''}`)
    },
    get: (id: string) => fetchJSON<Incident2>(`/incidents/${id}`),
    create: (data: { title: string; severity?: string; description?: string }) =>
      postJSON<Incident2>('/incidents', data),
    update: (id: string, data: Record<string, unknown>) =>
      patchJSON<Incident2>(`/incidents/${id}`, data),
    alerts: (id: string) => fetchJSON<Alert[]>(`/incidents/${id}/alerts`),
    activities: (id: string) => fetchJSON<ActivityList>(`/incidents/${id}/activities`),
    addComment: (id: string, text: string) =>
      postJSON<Activity>(`/incidents/${id}/comments`, { text }),
    editComment: (id: string, commentId: string, text: string) =>
      patchJSON<Activity>(`/incidents/${id}/comments/${commentId}`, { text }),
    observables: (id: string) => fetchJSON<Observable[]>(`/incidents/${id}/observables`),
    createObservable: (id: string, data: { type: string; value: string; source?: string }) =>
      postJSON<Observable>(`/incidents/${id}/observables`, data),
    linkAlert: (id: string, alertId: string) =>
      postJSON<{ detail: string }>(`/incidents/${id}/alerts`, { alert_id: alertId }),
    unlinkAlert: (id: string, alertId: string) =>
      deleteJSON(`/incidents/${id}/alerts/${alertId}`),
    suggestions: () => fetchJSON<IncidentSuggestion[]>('/incidents/suggestions'),
  },
  observables: {
    list: (params?: { type?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams()
      if (params?.type) qs.set('type', params.type)
      if (params?.limit) qs.set('limit', String(params.limit))
      if (params?.offset) qs.set('offset', String(params.offset))
      const q = qs.toString()
      return fetchJSON<{ observables: Observable[]; total: number }>(`/observables${q ? `?${q}` : ''}`)
    },
    get: (id: string) => fetchJSON<Observable>(`/observables/${id}`),
    create: (data: { type: string; value: string; source?: string }) =>
      postJSON<Observable>('/observables', data),
  },
  tenants: {
    list: () => fetchJSON<TenantInfo[]>('/tenants'),
    globalResources: () => fetchJSON<GlobalResourceInventory>('/tenants/admin/global-resources'),
    create: (data: {
      name: string
      slug: string
      legacy_partner_key?: string | null
      config?: Record<string, unknown>
      analyst_ids?: string[]
      tenant_admin_ids?: string[]
    }) => postJSON<TenantInfo>('/tenants', data as Record<string, unknown>),
    update: (id: string, data: {
      name?: string
      slug?: string
      legacy_partner_key?: string | null
      is_active?: boolean
      config?: Record<string, unknown>
      analyst_ids?: string[]
      tenant_admin_ids?: string[]
    }) => patchJSON<TenantInfo>(`/tenants/${id}`, data as Record<string, unknown>),
    remove: (id: string) => deleteJSON(`/tenants/${id}`),
  },
  ssoProviders: {
    list: () => fetchJSON<SSOProviderInfo[]>('/sso/providers'),
    create: (data: {
      provider_type?: string
      name: string
      issuer: string
      client_id: string
      client_secret: string
      authorize_url: string
      token_url: string
      userinfo_url?: string
      jwks_uri?: string
      scope?: string
      enabled?: boolean
      extra_config?: Record<string, unknown>
    }) => postJSON<SSOProviderInfo>('/sso/providers', data as Record<string, unknown>),
    update: (id: string, data: {
      name?: string
      issuer?: string
      client_id?: string
      client_secret?: string
      authorize_url?: string
      token_url?: string
      userinfo_url?: string | null
      jwks_uri?: string | null
      scope?: string
      enabled?: boolean
      extra_config?: Record<string, unknown>
    }) => patchJSON<SSOProviderInfo>(`/sso/providers/${id}`, data as Record<string, unknown>),
    remove: (id: string) => deleteJSON(`/sso/providers/${id}`),
  },
  dashboard: {
    stats: (tenantId?: string) => fetchJSON<DashboardStats>(`/dashboard/stats${tenantId ? `?tenant_id=${tenantId}` : ''}`),
  },
  reportSchedules: {
    list: () => fetchJSON<ReportScheduleInfo[]>('/compliance/reports/schedules'),
    create: (data: {
      report_type: string
      format: string
      cadence: string
      destination_email?: string
      tenant_id?: string | null
      is_active?: boolean
      config?: Record<string, unknown>
    }) => postJSON<ReportScheduleInfo>('/compliance/reports/schedules', data as Record<string, unknown>),
    update: (id: string, data: {
      cadence?: string
      destination_email?: string
      tenant_id?: string | null
      is_active?: boolean
      config?: Record<string, unknown>
    }) => patchJSON<ReportScheduleInfo>(`/compliance/reports/schedules/${id}`, data as Record<string, unknown>),
    remove: (id: string) => deleteJSON(`/compliance/reports/schedules/${id}`),
    run: (id: string) => postJSON<{ detail: string; execution: Record<string, unknown>; schedule: ReportScheduleInfo }>(`/compliance/reports/schedules/${id}/run`, {}),
  },
  dataRetention: {
    get: () => fetchJSON<DataRetentionPolicyInfo>('/compliance/data-retention'),
    update: (data: {
      audit_log_retention_days?: number | null
      report_run_retention_days?: number | null
      auto_apply_enabled: boolean
      notes?: string | null
    }) => putJSON<DataRetentionPolicyInfo>('/compliance/data-retention', data as Record<string, unknown>),
    enforce: () => postJSON<DataRetentionEnforcementInfo>('/compliance/data-retention/enforce', {}),
  },
}
