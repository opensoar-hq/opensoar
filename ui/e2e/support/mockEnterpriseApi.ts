import type { Page, Route } from '@playwright/test'

interface AuthProviderCapability {
  id: string
  name: string
  type: string
  login_url: string | null
}

interface AuthCapabilities {
  local_login_enabled: boolean
  local_registration_enabled: boolean
  providers: AuthProviderCapability[]
}

interface Analyst {
  id: string
  username: string
  display_name: string
  email: string | null
  is_active: boolean
  has_local_password: boolean
  role: string
  created_at: string
}

interface AnalystRole {
  id: string
  label: string
}

interface ApiKeyInfo {
  id: string
  name: string
  prefix: string
  is_active: boolean
  created_at: string
  key?: string
}

interface ApiKeyScopeInfo {
  api_key_id: string
  scopes: string[]
  tenant_id: string | null
}

interface TenantInfo {
  id: string
  name: string
  slug: string
  legacy_partner_key: string | null
  is_active: boolean
  config: Record<string, unknown>
  alert_count: number
  analyst_count: number
}

interface SSOProviderInfo {
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

interface ReportScheduleInfo {
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

interface DataRetentionPolicyInfo {
  id: string
  audit_log_retention_days: number | null
  report_run_retention_days: number | null
  auto_apply_enabled: boolean
  last_enforced_at: string | null
  last_enforcement_summary: Record<string, unknown> | null
  notes: string | null
}

interface MockEnterpriseState {
  authenticated: boolean
  analyst: Analyst | null
  authCapabilities: AuthCapabilities
  analystRoles: AnalystRole[]
  analysts: Analyst[]
  integrations: {
    id: string
    integration_type: string
    name: string
    partner: string | null
    enabled: boolean
    health_status: string | null
    last_health_check: string | null
    created_at: string
  }[]
  playbooks: {
    id: string
    name: string
    description: string | null
    partner: string | null
    module_path: string
    function_name: string
    trigger_type: string | null
    trigger_config: Record<string, unknown>
    enabled: boolean
    version: number
    created_at: string
  }[]
  apiKeys: ApiKeyInfo[]
  apiKeyScopes: Record<string, ApiKeyScopeInfo>
  tenants: TenantInfo[]
  providers: SSOProviderInfo[]
  schedules: ReportScheduleInfo[]
  dataRetention: DataRetentionPolicyInfo
}

interface MockEnterpriseOptions {
  authenticated?: boolean
  analyst?: Analyst | null
  authCapabilities?: AuthCapabilities
  analystRoles?: AnalystRole[]
  analysts?: Analyst[]
  integrations?: {
    id: string
    integration_type: string
    name: string
    partner: string | null
    enabled: boolean
    health_status: string | null
    last_health_check: string | null
    created_at: string
  }[]
  playbooks?: {
    id: string
    name: string
    description: string | null
    partner: string | null
    module_path: string
    function_name: string
    trigger_type: string | null
    trigger_config: Record<string, unknown>
    enabled: boolean
    version: number
    created_at: string
  }[]
  apiKeys?: ApiKeyInfo[]
  apiKeyScopes?: Record<string, ApiKeyScopeInfo>
  tenants?: TenantInfo[]
  providers?: SSOProviderInfo[]
  schedules?: ReportScheduleInfo[]
  dataRetention?: DataRetentionPolicyInfo
}

const now = '2026-04-04T00:00:00.000Z'

const defaultAdmin: Analyst = {
  id: 'analyst-admin',
  username: 'admin',
  display_name: 'Admin Analyst',
  email: 'admin@opensoar.app',
  is_active: true,
  has_local_password: true,
  role: 'admin',
  created_at: now,
}

const defaultAnalyst: Analyst = {
  id: 'analyst-standard',
  username: 'standard',
  display_name: 'Standard Analyst',
  email: 'analyst@opensoar.app',
  is_active: true,
  has_local_password: true,
  role: 'analyst',
  created_at: now,
}

let idCounter = 1

function nextId(prefix: string): string {
  idCounter += 1
  return `${prefix}-${idCounter}`
}

function cloneState(options: MockEnterpriseOptions): MockEnterpriseState {
  const apiKeys = options.apiKeys ?? [
    {
      id: 'key-1',
      name: 'Webhook Ingest',
      prefix: 'osk_live',
      is_active: true,
      created_at: now,
    },
  ]

  return {
    authenticated: options.authenticated ?? true,
    analyst: options.analyst ?? { ...defaultAdmin },
    authCapabilities: options.authCapabilities ?? {
      local_login_enabled: true,
      local_registration_enabled: false,
      providers: [],
    },
    analystRoles: options.analystRoles ?? [
      { id: 'admin', label: 'Admin' },
      { id: 'analyst', label: 'Analyst' },
      { id: 'viewer', label: 'Viewer' },
      { id: 'tenant_admin', label: 'Tenant Admin' },
      { id: 'playbook_author', label: 'Playbook Author' },
    ],
    analysts: options.analysts ?? [{ ...defaultAdmin }, { ...defaultAnalyst }],
    integrations: options.integrations ?? [
      {
        id: 'integration-1',
        integration_type: 'slack',
        name: 'Global Slack',
        partner: null,
        enabled: true,
        health_status: null,
        last_health_check: null,
        created_at: now,
      },
    ],
    playbooks: options.playbooks ?? [
      {
        id: 'playbook-1',
        name: 'Northwind Playbook',
        description: null,
        partner: 'northwind',
        module_path: 'playbooks.northwind',
        function_name: 'run',
        trigger_type: 'webhook',
        trigger_config: {},
        enabled: true,
        version: 1,
        created_at: now,
      },
      {
        id: 'playbook-2',
        name: 'Global Playbook',
        description: null,
        partner: null,
        module_path: 'playbooks.global',
        function_name: 'run',
        trigger_type: 'webhook',
        trigger_config: {},
        enabled: true,
        version: 1,
        created_at: now,
      },
    ],
    apiKeys,
    apiKeyScopes: options.apiKeyScopes ?? {
      [apiKeys[0].id]: {
        api_key_id: apiKeys[0].id,
        scopes: ['alerts:read'],
        tenant_id: null,
      },
    },
    tenants: options.tenants ?? [
      {
        id: 'tenant-1',
        name: 'Northwind Operations',
        slug: 'northwind-ops',
        legacy_partner_key: 'northwind',
        is_active: true,
        config: {},
        alert_count: 4,
        analyst_count: 2,
      },
    ],
    providers: options.providers ?? [],
    schedules: options.schedules ?? [],
    dataRetention: options.dataRetention ?? {
      id: 'retention-1',
      audit_log_retention_days: 365,
      report_run_retention_days: 90,
      auto_apply_enabled: false,
      last_enforced_at: null,
      last_enforcement_summary: null,
      notes: null,
    },
  }
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

function requestBody(route: Route): Record<string, unknown> {
  return (route.request().postDataJSON() ?? {}) as Record<string, unknown>
}

function findId(pathname: string): string {
  return pathname.split('/').at(-1) ?? ''
}

export async function mockEnterpriseApi(
  page: Page,
  options: MockEnterpriseOptions = {},
): Promise<MockEnterpriseState> {
  const state = cloneState(options)

  await page.addInitScript((token: string | null) => {
    if (token) {
      window.localStorage.setItem('opensoar_token', token)
      return
    }
    window.localStorage.removeItem('opensoar_token')
  }, state.authenticated ? 'mock-admin-token' : null)

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const pathname = new URL(request.url()).pathname

    if (method === 'GET' && pathname === '/api/v1/auth/capabilities') {
      await fulfillJson(route, state.authCapabilities)
      return
    }

    if (method === 'GET' && pathname === '/api/v1/auth/me') {
      if (!state.authenticated || !state.analyst) {
        await fulfillJson(route, { detail: 'Unauthorized' }, 401)
        return
      }
      await fulfillJson(route, state.analyst)
      return
    }

    if (method === 'GET' && pathname === '/api/v1/auth/analysts') {
      await fulfillJson(route, state.analysts)
      return
    }

    if (method === 'POST' && pathname === '/api/v1/auth/change-password') {
      await fulfillJson(route, { detail: 'Password updated' })
      return
    }

    if (method === 'GET' && pathname === '/api/v1/auth/roles') {
      await fulfillJson(route, state.analystRoles)
      return
    }

    if (method === 'POST' && pathname === '/api/v1/auth/analysts') {
      const body = requestBody(route)
      const analyst: Analyst = {
        id: nextId('analyst'),
        username: String(body.username ?? ''),
        display_name: String(body.display_name ?? body.username ?? ''),
        email: typeof body.email === 'string' ? body.email : null,
        is_active: true,
        has_local_password: true,
        role: typeof body.role === 'string' ? body.role : 'analyst',
        created_at: now,
      }
      state.analysts.push(analyst)
      await fulfillJson(route, analyst, 201)
      return
    }

    if (method === 'GET' && pathname === '/api/v1/integrations') {
      await fulfillJson(route, state.integrations)
      return
    }

    if (pathname.startsWith('/api/v1/integrations/')) {
      const integrationId = findId(pathname)
      const integration = state.integrations.find((item) => item.id === integrationId)
      if (!integration) {
        await fulfillJson(route, { detail: 'Integration not found' }, 404)
        return
      }

      if (method === 'PATCH') {
        const body = requestBody(route)
        Object.assign(integration, {
          partner: typeof body.partner === 'string' ? body.partner : null,
          enabled: typeof body.enabled === 'boolean' ? body.enabled : integration.enabled,
        })
        await fulfillJson(route, integration)
        return
      }
    }

    if (method === 'GET' && pathname === '/api/v1/playbooks') {
      const tenantId = new URL(request.url()).searchParams.get('tenant_id')
      const playbooks = tenantId === 'tenant-1'
        ? state.playbooks.filter((item) => item.partner === 'northwind')
        : state.playbooks
      await fulfillJson(route, playbooks)
      return
    }

    if (pathname.startsWith('/api/v1/playbooks/')) {
      const playbookId = findId(pathname)
      const playbook = state.playbooks.find((item) => item.id === playbookId)
      if (!playbook) {
        await fulfillJson(route, { detail: 'Playbook not found' }, 404)
        return
      }

      if (method === 'PATCH') {
        const body = requestBody(route)
        Object.assign(playbook, {
          partner: typeof body.partner === 'string' ? body.partner : null,
          enabled: typeof body.enabled === 'boolean' ? body.enabled : playbook.enabled,
        })
        await fulfillJson(route, playbook)
        return
      }
    }

    if (method === 'GET' && pathname === '/api/v1/dashboard/stats') {
      const tenantId = new URL(request.url()).searchParams.get('tenant_id')
      const partner = tenantId === 'tenant-1' ? 'Northwind Operations' : 'All Partners'
      await fulfillJson(route, {
        alerts_by_severity: { high: 1 },
        alerts_by_status: { new: 1 },
        alerts_by_partner: { [partner]: 1 },
        alerts_by_determination: { unknown: 1 },
        open_by_partner: { [partner]: 1 },
        mttr_by_partner: { [partner]: 3600 },
        total_alerts: 1,
        total_runs: 1,
        open_alerts: 1,
        alerts_today: 1,
        active_runs: 0,
        unassigned_count: 1,
        mttr_seconds: 3600,
        priority_queue: [],
        my_alerts: [],
        recent_alerts: [],
        recent_runs: [],
      })
      return
    }

    if (method === 'GET' && pathname === '/api/v1/incidents') {
      const tenantId = new URL(request.url()).searchParams.get('tenant_id')
      const incidents = tenantId === 'tenant-1'
        ? [
            {
              id: 'incident-1',
              title: 'Northwind Workspace Incident',
              description: null,
              severity: 'high',
              status: 'open',
              assigned_to: null,
              assigned_username: null,
              tags: null,
              alert_count: 1,
              closed_at: null,
              created_at: now,
              updated_at: now,
            },
          ]
        : [
            {
              id: 'incident-1',
              title: 'Northwind Workspace Incident',
              description: null,
              severity: 'high',
              status: 'open',
              assigned_to: null,
              assigned_username: null,
              tags: null,
              alert_count: 1,
              closed_at: null,
              created_at: now,
              updated_at: now,
            },
            {
              id: 'incident-2',
              title: 'Global Incident',
              description: null,
              severity: 'medium',
              status: 'open',
              assigned_to: null,
              assigned_username: null,
              tags: null,
              alert_count: 2,
              closed_at: null,
              created_at: now,
              updated_at: now,
            },
          ]
      await fulfillJson(route, { incidents, total: incidents.length })
      return
    }

    if (method === 'GET' && pathname === '/api/v1/runs') {
      const tenantId = new URL(request.url()).searchParams.get('tenant_id')
      const runs = tenantId === 'tenant-1'
        ? [
            {
              id: 'run-1',
              playbook_id: 'playbook-1',
              alert_id: 'alert-1',
              status: 'completed',
              started_at: now,
              finished_at: now,
              error: null,
              result: {},
              action_results: [],
              created_at: now,
            },
          ]
        : [
            {
              id: 'run-1',
              playbook_id: 'playbook-1',
              alert_id: 'alert-1',
              status: 'completed',
              started_at: now,
              finished_at: now,
              error: null,
              result: {},
              action_results: [],
              created_at: now,
            },
            {
              id: 'run-2',
              playbook_id: 'playbook-2',
              alert_id: 'alert-2',
              status: 'failed',
              started_at: now,
              finished_at: now,
              error: 'boom',
              result: {},
              action_results: [],
              created_at: now,
            },
          ]
      await fulfillJson(route, { runs, total: runs.length })
      return
    }

    if (pathname.startsWith('/api/v1/auth/analysts/')) {
      const analystId = findId(pathname)
      const analyst = state.analysts.find((item) => item.id === analystId)
      if (!analyst) {
        await fulfillJson(route, { detail: 'Analyst not found' }, 404)
        return
      }

      if (method === 'PATCH') {
        const body = requestBody(route)
        Object.assign(analyst, {
          role: typeof body.role === 'string' ? body.role : analyst.role,
          is_active: typeof body.is_active === 'boolean' ? body.is_active : analyst.is_active,
        })
        await fulfillJson(route, analyst)
        return
      }

      if (method === 'POST' && pathname.endsWith('/reset-password')) {
        await fulfillJson(route, { detail: 'Password reset' })
        return
      }
    }

    if (method === 'GET' && pathname === '/api/v1/api-keys') {
      await fulfillJson(route, state.apiKeys)
      return
    }

    if (pathname.startsWith('/api/v1/api-key-scopes/')) {
      const keyId = findId(pathname)
      if (method === 'GET') {
        await fulfillJson(route, state.apiKeyScopes[keyId] ?? {
          api_key_id: keyId,
          scopes: [],
          tenant_id: null,
        })
        return
      }

      if (method === 'PUT') {
        const body = requestBody(route)
        state.apiKeyScopes[keyId] = {
          api_key_id: keyId,
          scopes: Array.isArray(body.scopes) ? body.scopes.map(String) : [],
          tenant_id: typeof body.tenant_id === 'string' ? body.tenant_id : null,
        }
        await fulfillJson(route, state.apiKeyScopes[keyId])
        return
      }
    }

    if (pathname === '/api/v1/tenants') {
      if (method === 'GET') {
        await fulfillJson(route, state.tenants)
        return
      }

      if (method === 'POST') {
        const body = requestBody(route)
        const analystIds = Array.isArray(body.analyst_ids) ? body.analyst_ids : []
        const tenant = {
          id: nextId('tenant'),
          name: String(body.name ?? ''),
          slug: String(body.slug ?? ''),
          legacy_partner_key: typeof body.legacy_partner_key === 'string' ? body.legacy_partner_key : null,
          is_active: true,
          config: typeof body.config === 'object' && body.config ? body.config as Record<string, unknown> : {},
          alert_count: 0,
          analyst_count: analystIds.length,
        }
        state.tenants.push(tenant)
        await fulfillJson(route, tenant, 201)
        return
      }
    }

    if (pathname.startsWith('/api/v1/tenants/')) {
      const tenantId = findId(pathname)
      const tenant = state.tenants.find((item) => item.id === tenantId)
      if (!tenant) {
        await fulfillJson(route, { detail: 'Tenant not found' }, 404)
        return
      }

      if (method === 'PATCH') {
        const body = requestBody(route)
        Object.assign(tenant, {
          name: typeof body.name === 'string' ? body.name : tenant.name,
          slug: typeof body.slug === 'string' ? body.slug : tenant.slug,
          legacy_partner_key: typeof body.legacy_partner_key === 'string' ? body.legacy_partner_key : tenant.legacy_partner_key,
          is_active: typeof body.is_active === 'boolean' ? body.is_active : tenant.is_active,
          config: typeof body.config === 'object' && body.config ? body.config as Record<string, unknown> : tenant.config,
        })
        await fulfillJson(route, tenant)
        return
      }

      if (method === 'DELETE') {
        state.tenants = state.tenants.filter((item) => item.id !== tenantId)
        await fulfillJson(route, { detail: 'Tenant deactivated' })
        return
      }
    }

    if (pathname === '/api/v1/sso/providers') {
      if (method === 'GET') {
        await fulfillJson(route, state.providers)
        return
      }

      if (method === 'POST') {
        const body = requestBody(route)
        const provider = {
          id: nextId('provider'),
          provider_type: String(body.provider_type ?? 'oidc'),
          name: String(body.name ?? ''),
          issuer: String(body.issuer ?? ''),
          client_id: String(body.client_id ?? ''),
          authorize_url: String(body.authorize_url ?? ''),
          token_url: String(body.token_url ?? ''),
          userinfo_url: typeof body.userinfo_url === 'string' ? body.userinfo_url : null,
          jwks_uri: typeof body.jwks_uri === 'string' ? body.jwks_uri : null,
          scope: typeof body.scope === 'string' ? body.scope : 'openid profile email',
          enabled: typeof body.enabled === 'boolean' ? body.enabled : true,
          extra_config: typeof body.extra_config === 'object' && body.extra_config ? body.extra_config as Record<string, unknown> : {},
        }
        state.providers.push(provider)
        await fulfillJson(route, provider, 201)
        return
      }
    }

    if (pathname.startsWith('/api/v1/sso/providers/')) {
      const providerId = findId(pathname)
      const provider = state.providers.find((item) => item.id === providerId)
      if (!provider) {
        await fulfillJson(route, { detail: 'Provider not found' }, 404)
        return
      }

      if (method === 'PATCH') {
        const body = requestBody(route)
        Object.assign(provider, {
          name: typeof body.name === 'string' ? body.name : provider.name,
          issuer: typeof body.issuer === 'string' ? body.issuer : provider.issuer,
          client_id: typeof body.client_id === 'string' ? body.client_id : provider.client_id,
          authorize_url: typeof body.authorize_url === 'string' ? body.authorize_url : provider.authorize_url,
          token_url: typeof body.token_url === 'string' ? body.token_url : provider.token_url,
          userinfo_url: typeof body.userinfo_url === 'string' ? body.userinfo_url : provider.userinfo_url,
          jwks_uri: typeof body.jwks_uri === 'string' ? body.jwks_uri : provider.jwks_uri,
          scope: typeof body.scope === 'string' ? body.scope : provider.scope,
          enabled: typeof body.enabled === 'boolean' ? body.enabled : provider.enabled,
          extra_config: typeof body.extra_config === 'object' && body.extra_config ? body.extra_config as Record<string, unknown> : provider.extra_config,
        })
        await fulfillJson(route, provider)
        return
      }

      if (method === 'DELETE') {
        state.providers = state.providers.filter((item) => item.id !== providerId)
        await fulfillJson(route, { detail: 'OIDC provider deleted' })
        return
      }
    }

    if (pathname === '/api/v1/compliance/reports/schedules') {
      if (method === 'GET') {
        await fulfillJson(route, state.schedules)
        return
      }

      if (method === 'POST') {
        const body = requestBody(route)
        const schedule = {
          id: nextId('schedule'),
          report_type: String(body.report_type ?? 'audit_log'),
          format: String(body.format ?? 'pdf'),
          cadence: String(body.cadence ?? 'manual'),
          destination_email: typeof body.destination_email === 'string' ? body.destination_email : null,
          tenant_id: typeof body.tenant_id === 'string' ? body.tenant_id : null,
          is_active: typeof body.is_active === 'boolean' ? body.is_active : true,
          config: typeof body.config === 'object' && body.config ? body.config as Record<string, unknown> : {},
          last_run_at: null,
          last_run_status: null,
          last_run_detail: null,
        }
        state.schedules.push(schedule)
        await fulfillJson(route, schedule, 201)
        return
      }
    }

    if (pathname === '/api/v1/compliance/data-retention') {
      if (method === 'GET') {
        await fulfillJson(route, state.dataRetention)
        return
      }

      if (method === 'PUT') {
        const body = requestBody(route)
        state.dataRetention = {
          ...state.dataRetention,
          audit_log_retention_days: typeof body.audit_log_retention_days === 'number' ? body.audit_log_retention_days : null,
          report_run_retention_days: typeof body.report_run_retention_days === 'number' ? body.report_run_retention_days : null,
          auto_apply_enabled: Boolean(body.auto_apply_enabled),
          notes: typeof body.notes === 'string' ? body.notes : null,
        }
        await fulfillJson(route, state.dataRetention)
        return
      }
    }

    if (method === 'GET' && pathname === '/api/v1/tenants/admin/global-resources') {
      await fulfillJson(route, {
        integrations: state.integrations
          .filter((item) => item.partner === null)
          .map((item) => ({
            id: item.id,
            name: item.name,
            resource_type: 'integration',
            created_at: item.created_at,
          })),
        playbooks: state.playbooks
          .filter((item) => item.partner === null)
          .map((item) => ({
            id: item.id,
            name: item.name,
            resource_type: 'playbook',
            created_at: item.created_at,
          })),
      })
      return
    }

    if (pathname === '/api/v1/compliance/data-retention/enforce' && method === 'POST') {
      state.dataRetention = {
        ...state.dataRetention,
        last_enforced_at: new Date().toISOString(),
        last_enforcement_summary: {
          audit_log_entries_deleted: 3,
          report_runs_cleared: 1,
        },
      }
      await fulfillJson(route, {
        audit_log_entries_deleted: 3,
        report_runs_cleared: 1,
        enforced_at: state.dataRetention.last_enforced_at,
      })
      return
    }

    if (pathname.startsWith('/api/v1/compliance/reports/schedules/')) {
      const segments = pathname.split('/')
      const scheduleId = segments[segments.length - (segments.at(-1) === 'run' ? 2 : 1)] ?? ''
      const schedule = state.schedules.find((item) => item.id === scheduleId)
      if (!schedule) {
        await fulfillJson(route, { detail: 'Report schedule not found' }, 404)
        return
      }

      if (method === 'POST' && pathname.endsWith('/run')) {
        schedule.last_run_at = new Date().toISOString()
        schedule.last_run_status = 'success'
        schedule.last_run_detail = `Generated ${schedule.report_type}.${schedule.format}`
        await fulfillJson(route, {
          detail: 'Report schedule executed',
          execution: {
            filename: `${schedule.report_type}.${schedule.format}`,
            media_type: schedule.format === 'pdf' ? 'application/pdf' : 'application/json',
            size: 512,
          },
          schedule,
        })
        return
      }

      if (method === 'DELETE') {
        state.schedules = state.schedules.filter((item) => item.id !== scheduleId)
        await fulfillJson(route, { detail: 'Report schedule deleted' })
        return
      }
    }

    await fulfillJson(
      route,
      {
        detail: `No mock route for ${method} ${pathname}`,
      },
      404,
    )
  })

  return state
}
