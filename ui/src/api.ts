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
  role: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  analyst: Analyst
}

export interface Activity {
  id: string
  alert_id: string
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
  },
  webhooks: {
    createAlert: (payload: Record<string, unknown>) =>
      postJSON<WebhookResponse>('/webhooks/alerts', payload),
  },
  alerts: {
    list: (params?: { status?: string; severity?: string; source?: string; partner?: string; determination?: string; search?: string; limit?: number; offset?: number }) => {
      const sp = new URLSearchParams()
      if (params?.status) sp.set('status', params.status)
      if (params?.severity) sp.set('severity', params.severity)
      if (params?.source) sp.set('source', params.source)
      if (params?.partner) sp.set('partner', params.partner)
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
    getActivities: (alertId: string) => fetchJSON<ActivityList>(`/alerts/${alertId}/activities`),
    addComment: (alertId: string, text: string) =>
      postJSON<Activity>(`/alerts/${alertId}/comments`, { text }),
    editComment: (alertId: string, commentId: string, text: string) =>
      patchJSON<Activity>(`/alerts/${alertId}/comments/${commentId}`, { text }),
    bulk: (data: { alert_ids: string[]; action: string; resolve_reason?: string; determination?: string; severity?: string }) =>
      postJSON<BulkOperationResult>('/alerts/bulk', data),
  },
  playbooks: {
    list: () => fetchJSON<Playbook[]>('/playbooks'),
    get: (id: string) => fetchJSON<Playbook>(`/playbooks/${id}`),
    update: (id: string, data: { enabled?: boolean }) =>
      patchJSON<Playbook>(`/playbooks/${id}`, data),
    run: (id: string, data?: { alert_id?: string }) =>
      postJSON<{ message: string; celery_task_id: string }>(`/playbooks/${id}/run`, data || {}),
  },
  runs: {
    list: (params?: { status?: string; playbook_id?: string; limit?: number; offset?: number }) => {
      const sp = new URLSearchParams()
      if (params?.status) sp.set('status', params.status)
      if (params?.playbook_id) sp.set('playbook_id', params.playbook_id)
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
    create: (data: { integration_type: string; name: string; config: Record<string, unknown>; enabled?: boolean }) =>
      postJSON<Integration>('/integrations', data),
    update: (id: string, data: { name?: string; config?: Record<string, unknown>; enabled?: boolean }) =>
      patchJSON<Integration>(`/integrations/${id}`, data),
    delete: (id: string) => deleteJSON(`/integrations/${id}`),
    healthCheck: (id: string) => postJSON<{ healthy: boolean; message: string; details: Record<string, unknown> | null }>(`/integrations/${id}/health`, {}),
  },
  apiKeys: {
    list: () => fetchJSON<ApiKeyInfo[]>('/api-keys'),
    create: (data: { name: string }) => postJSON<ApiKeyInfo>('/api-keys', data),
    revoke: (id: string) => deleteJSON(`/api-keys/${id}`),
  },
  analysts: {
    list: () => fetchJSON<Analyst[]>('/auth/analysts'),
    update: (id: string, data: { display_name?: string; email?: string; is_active?: boolean; role?: string }) =>
      patchJSON<Analyst>(`/auth/analysts/${id}`, data),
  },
  dashboard: {
    stats: () => fetchJSON<DashboardStats>('/dashboard/stats'),
  },
}
