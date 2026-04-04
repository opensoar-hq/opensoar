import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings, Plug, Key, Users, Plus, Trash2, Shield,
  CheckCircle, XCircle, Copy, Heart, Loader2, CalendarDays, Play, Building2,
} from 'lucide-react'
import { api, type Integration } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { Button } from '@/components/ui/Button'
import { Tabs } from '@/components/ui/Tabs'
import { Card } from '@/components/ui/Card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/Dialog'
import { Input, Textarea, Label } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageTransition } from '@/components/ui/PageTransition'
import { useToast } from '@/components/ui/Toast'
import { useAuth } from '@/contexts/AuthContext'

const ease = [0.25, 0.1, 0.25, 1] as [number, number, number, number]

type Tab = 'integrations' | 'api-keys' | 'analysts' | 'enterprise'

function IntegrationsTab() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [showDialog, setShowDialog] = useState(false)
  const [form, setForm] = useState({ integration_type: '', name: '', config: '{}' })

  const { data: integrations, isLoading } = useQuery({
    queryKey: ['integrations'],
    queryFn: api.integrations.list,
  })

  const { data: availableTypes } = useQuery({
    queryKey: ['integration-types'],
    queryFn: api.integrations.types,
  })

  const healthMutation = useMutation({
    mutationFn: (id: string) => api.integrations.healthCheck(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
    },
    onError: () => {
      toast.error('Health check failed')
    },
  })

  const createMutation = useMutation({
    mutationFn: () => {
      let config: Record<string, unknown> = {}
      try { config = JSON.parse(form.config) } catch { /* keep empty */ }
      return api.integrations.create({
        integration_type: form.integration_type,
        name: form.name,
        config,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      setShowDialog(false)
      setForm({ integration_type: '', name: '', config: '{}' })
      toast.success('Integration created')
    },
    onError: () => {
      toast.error('Failed to create integration')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (i: Integration) => api.integrations.update(i.id, { enabled: !i.enabled }),
    onSuccess: (_data, i) => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      toast.success(`Integration ${i.enabled ? 'disabled' : 'enabled'}`)
    },
    onError: () => {
      toast.error('Failed to update integration')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.integrations.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      toast.success('Integration deleted')
    },
    onError: () => {
      toast.error('Failed to delete integration')
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        <CardSkeleton lines={2} />
        <CardSkeleton lines={2} />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-heading m-0">Configured Integrations</h3>
        <Button size="sm" onClick={() => setShowDialog(true)}>
          <Plus size={14} /> Add Integration
        </Button>
      </div>

      <Dialog open={showDialog} onClose={() => setShowDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowDialog(false)}>
            <DialogTitle>Add Integration</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Type</Label>
                <Select
                  value={form.integration_type}
                  onChange={(v) => setForm({ ...form, integration_type: v })}
                  options={[
                    { value: '', label: 'Select type...' },
                    ...(availableTypes || []).map((t) => ({
                      value: t.type,
                      label: t.display_name,
                    })),
                  ]}
                  className="w-full"
                />
              </div>
              <div>
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="My VirusTotal"
                />
              </div>
            </div>
            <div>
              <Label>Config (JSON)</Label>
              <Textarea
                value={form.config}
                onChange={(e) => setForm({ ...form, config: e.target.value })}
                rows={3}
                placeholder='{"api_key": "your-key-here"}'
                className="font-mono"
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowDialog(false)}>Cancel</Button>
            <Button size="sm" variant="primary" onClick={() => createMutation.mutate()} disabled={!form.integration_type || !form.name}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {integrations && integrations.length > 0 ? (
        <Card>
          {integrations.map((int) => (
            <div key={int.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
              <Plug size={14} className="text-muted shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-heading font-medium">{int.name}</div>
                <div className="text-[11px] text-muted">{int.integration_type}</div>
              </div>
              {int.health_status && (
                <span className={`text-[11px] px-2 py-0.5 rounded ${int.health_status === 'healthy' ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>
                  {int.health_status}
                </span>
              )}
              <span className={`text-[11px] px-2 py-0.5 rounded ${int.enabled ? 'bg-success/15 text-success' : 'bg-muted/15 text-muted'}`}>
                {int.enabled ? 'Enabled' : 'Disabled'}
              </span>
              <button
                onClick={() => healthMutation.mutate(int.id)}
                disabled={healthMutation.isPending}
                className="p-1.5 rounded hover:bg-surface text-muted hover:text-heading bg-transparent border-none cursor-pointer disabled:opacity-50"
                title="Run health check"
              >
                {healthMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Heart size={13} />}
              </button>
              <Button size="sm" variant="ghost" onClick={() => toggleMutation.mutate(int)}>
                {int.enabled ? 'Disable' : 'Enable'}
              </Button>
              <button
                onClick={() => deleteMutation.mutate(int.id)}
                className="p-1.5 rounded hover:bg-danger/10 text-muted hover:text-danger bg-transparent border-none cursor-pointer"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </Card>
      ) : (
        <EmptyState icon={<Plug size={28} />} title="No integrations" description="Add an integration to connect external services" />
      )}
    </div>
  )
}

function ApiKeysTab() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [showDialog, setShowDialog] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [newKey, setNewKey] = useState<string | null>(null)

  const { data: keys, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: api.apiKeys.list,
  })

  const createMutation = useMutation({
    mutationFn: () => api.apiKeys.create({ name: keyName }),
    onSuccess: (data) => {
      setNewKey(data.key || null)
      setKeyName('')
      setShowDialog(false)
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast.success('API key created')
    },
    onError: () => {
      toast.error('Failed to create API key')
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.apiKeys.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast.success('API key revoked')
    },
    onError: () => {
      toast.error('Failed to revoke API key')
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        <CardSkeleton lines={1} />
        <CardSkeleton lines={1} />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-heading m-0">API Keys</h3>
        <Button size="sm" onClick={() => { setShowDialog(true); setNewKey(null) }}>
          <Plus size={14} /> Create Key
        </Button>
      </div>

      <Dialog open={showDialog} onClose={() => setShowDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowDialog(false)}>
            <DialogTitle>Create API Key</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Label>Key Name</Label>
            <Input
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="Key name (e.g. CI/CD Pipeline)"
            />
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowDialog(false)}>Cancel</Button>
            <Button size="sm" variant="primary" onClick={() => createMutation.mutate()} disabled={!keyName}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {newKey && (
        <div className="border border-success/30 rounded-lg bg-success/10 p-4 mb-4">
          <div className="text-xs text-success font-medium mb-2">API key created — copy it now, it won't be shown again:</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono text-heading bg-bg px-3 py-2 rounded border border-border overflow-x-auto">
              {newKey}
            </code>
            <button
              onClick={() => { navigator.clipboard.writeText(newKey); toast.success('Copied to clipboard') }}
              className="p-2 rounded hover:bg-surface bg-transparent border-none cursor-pointer text-muted hover:text-heading"
            >
              <Copy size={14} />
            </button>
          </div>
        </div>
      )}

      {keys && keys.length > 0 ? (
        <Card>
          {keys.map((k) => (
            <div key={k.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
              <Key size={14} className="text-muted shrink-0" />
              <div className="flex-1">
                <div className="text-sm text-heading">{k.name}</div>
                <div className="text-[11px] text-muted font-mono">{k.prefix}...</div>
              </div>
              {k.is_active ? (
                <CheckCircle size={13} className="text-success" />
              ) : (
                <XCircle size={13} className="text-danger" />
              )}
              {k.is_active && (
                <Button size="sm" variant="ghost" onClick={() => revokeMutation.mutate(k.id)}>
                  Revoke
                </Button>
              )}
            </div>
          ))}
        </Card>
      ) : (
        <EmptyState icon={<Key size={28} />} title="No API keys" description="Create an API key to authenticate external services" />
      )}
    </div>
  )
}

function AnalystsTab() {
  const queryClient = useQueryClient()
  const toast = useToast()

  const { data: analysts, isLoading } = useQuery({
    queryKey: ['analysts'],
    queryFn: api.analysts.list,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { is_active?: boolean; role?: string } }) =>
      api.analysts.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysts'] })
      toast.success('Analyst updated')
    },
    onError: () => {
      toast.error('Failed to update analyst')
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        <CardSkeleton lines={1} />
        <CardSkeleton lines={1} />
      </div>
    )
  }

  return (
    <div>
      <h3 className="text-sm font-medium text-heading m-0 mb-4">Analysts</h3>
      {analysts && analysts.length > 0 ? (
        <Card>
          {analysts.map((a) => (
            <div key={a.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
              <Users size={14} className="text-muted shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-heading">{a.display_name}</div>
                <div className="text-[11px] text-muted">@{a.username} {a.email ? `· ${a.email}` : ''}</div>
              </div>
              <Select
                value={a.role}
                onChange={(v) => updateMutation.mutate({ id: a.id, data: { role: v } })}
                options={[
                  { value: 'analyst', label: 'Analyst' },
                  { value: 'admin', label: 'Admin' },
                ]}
              />
              <span className={`text-[11px] px-2 py-0.5 rounded ${a.is_active ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>
                {a.is_active ? 'Active' : 'Inactive'}
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => updateMutation.mutate({ id: a.id, data: { is_active: !a.is_active } })}
              >
                {a.is_active ? 'Deactivate' : 'Activate'}
              </Button>
            </div>
          ))}
        </Card>
      ) : (
        <EmptyState icon={<Users size={28} />} title="No analysts" description="Analysts will appear here after registration" />
      )}
    </div>
  )
}

function EnterpriseTab() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: analysts } = useQuery({
    queryKey: ['analysts'],
    queryFn: api.analysts.list,
  })

  const { data: tenants, isLoading: tenantsLoading, isError: tenantsUnavailable } = useQuery({
    queryKey: ['ee-tenants'],
    queryFn: api.tenants.list,
    retry: false,
  })

  const providersQuery = useQuery({
    queryKey: ['ee-sso-providers'],
    queryFn: api.ssoProviders.list,
    retry: false,
  })

  const [showScopeDialog, setShowScopeDialog] = useState(false)
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)
  const [scopeText, setScopeText] = useState('')
  const [scopeTenantId, setScopeTenantId] = useState('')
  const [showTenantDialog, setShowTenantDialog] = useState(false)
  const [editingTenantId, setEditingTenantId] = useState<string | null>(null)
  const [tenantForm, setTenantForm] = useState({
    name: '',
    slug: '',
    legacy_partner_key: '',
    partner_aliases: '',
    analyst_ids: [] as string[],
    tenant_admin_ids: [] as string[],
    is_active: true,
  })
  const [showProviderDialog, setShowProviderDialog] = useState(false)
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null)
  const [providerForm, setProviderForm] = useState({
    name: '',
    issuer: '',
    client_id: '',
    client_secret: '',
    authorize_url: '',
    token_url: '',
    userinfo_url: '',
    jwks_uri: '',
    scope: 'openid profile email',
    enabled: true,
    extra_config: '{}',
  })
  const [showScheduleDialog, setShowScheduleDialog] = useState(false)
  const [scheduleForm, setScheduleForm] = useState({
    report_type: 'sla_compliance',
    format: 'pdf',
    cadence: 'daily',
    destination_email: '',
    tenant_id: '',
    config: '{}',
  })

  const { data: keys, isLoading: keysLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: api.apiKeys.list,
  })

  const schedulesQuery = useQuery({
    queryKey: ['ee-report-schedules'],
    queryFn: api.reportSchedules.list,
    retry: false,
  })

  const scopeQuery = useQuery({
    queryKey: ['ee-api-key-scope', selectedKeyId],
    queryFn: () => api.apiKeyScopes.get(selectedKeyId!),
    enabled: showScopeDialog && !!selectedKeyId,
    retry: false,
  })

  const updateScopesMutation = useMutation({
    mutationFn: () => api.apiKeyScopes.update(selectedKeyId!, {
      scopes: scopeText.split(',').map((s) => s.trim()).filter(Boolean),
      tenant_id: scopeTenantId || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-api-key-scope', selectedKeyId] })
      toast.success('Key scopes updated')
      setShowScopeDialog(false)
      setSelectedKeyId(null)
      setScopeText('')
      setScopeTenantId('')
    },
    onError: () => {
      toast.error('Failed to update key scopes')
    },
  })

  const createScheduleMutation = useMutation({
    mutationFn: () => api.reportSchedules.create({
      report_type: scheduleForm.report_type,
      format: scheduleForm.format,
      cadence: scheduleForm.cadence,
      destination_email: scheduleForm.destination_email || undefined,
      tenant_id: scheduleForm.tenant_id || null,
      config: (() => {
        try { return JSON.parse(scheduleForm.config) } catch { return {} }
      })(),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-report-schedules'] })
      toast.success('Report schedule created')
      setShowScheduleDialog(false)
      setScheduleForm({
        report_type: 'sla_compliance',
        format: 'pdf',
        cadence: 'daily',
        destination_email: '',
        tenant_id: '',
        config: '{}',
      })
    },
    onError: () => {
      toast.error('Failed to create report schedule')
    },
  })

  const runScheduleMutation = useMutation({
    mutationFn: (id: string) => api.reportSchedules.run(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-report-schedules'] })
      toast.success('Report schedule executed')
    },
    onError: () => {
      toast.error('Failed to execute report schedule')
    },
  })

  const deleteScheduleMutation = useMutation({
    mutationFn: (id: string) => api.reportSchedules.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-report-schedules'] })
      toast.success('Report schedule deleted')
    },
    onError: () => {
      toast.error('Failed to delete report schedule')
    },
  })

  const enterpriseUnavailable = schedulesQuery.isError

  const createTenantMutation = useMutation({
    mutationFn: () => {
      const config: Record<string, unknown> = {}
      const aliases = tenantForm.partner_aliases.split(',').map((s) => s.trim()).filter(Boolean)
      if (aliases.length > 0) config.partner_aliases = aliases

      const payload = {
        name: tenantForm.name,
        slug: tenantForm.slug,
        legacy_partner_key: tenantForm.legacy_partner_key || null,
        config,
        analyst_ids: tenantForm.analyst_ids,
        tenant_admin_ids: tenantForm.tenant_admin_ids,
      }

      return editingTenantId
        ? api.tenants.update(editingTenantId, { ...payload, is_active: tenantForm.is_active })
        : api.tenants.create(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-tenants'] })
      toast.success(`Tenant ${editingTenantId ? 'updated' : 'created'}`)
      setShowTenantDialog(false)
      setEditingTenantId(null)
      setTenantForm({
        name: '',
        slug: '',
        legacy_partner_key: '',
        partner_aliases: '',
        analyst_ids: [],
        tenant_admin_ids: [],
        is_active: true,
      })
    },
    onError: () => {
      toast.error(`Failed to ${editingTenantId ? 'update' : 'create'} tenant`)
    },
  })

  const deleteTenantMutation = useMutation({
    mutationFn: (id: string) => api.tenants.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-tenants'] })
      toast.success('Tenant deactivated')
    },
    onError: () => {
      toast.error('Failed to deactivate tenant')
    },
  })

  const createProviderMutation = useMutation({
    mutationFn: () => {
      const extra_config = (() => {
        try { return JSON.parse(providerForm.extra_config) } catch { return {} }
      })()

      const payload = {
        name: providerForm.name,
        issuer: providerForm.issuer,
        client_id: providerForm.client_id,
        authorize_url: providerForm.authorize_url,
        token_url: providerForm.token_url,
        userinfo_url: providerForm.userinfo_url || undefined,
        jwks_uri: providerForm.jwks_uri || undefined,
        scope: providerForm.scope,
        enabled: providerForm.enabled,
        extra_config,
        ...(providerForm.client_secret ? { client_secret: providerForm.client_secret } : {}),
      }

      return editingProviderId
        ? api.ssoProviders.update(editingProviderId, payload)
        : api.ssoProviders.create({ provider_type: 'oidc', client_secret: providerForm.client_secret, ...payload })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-sso-providers'] })
      toast.success(`OIDC provider ${editingProviderId ? 'updated' : 'created'}`)
      setShowProviderDialog(false)
      setEditingProviderId(null)
      setProviderForm({
        name: '',
        issuer: '',
        client_id: '',
        client_secret: '',
        authorize_url: '',
        token_url: '',
        userinfo_url: '',
        jwks_uri: '',
        scope: 'openid profile email',
        enabled: true,
        extra_config: '{}',
      })
    },
    onError: () => {
      toast.error(`Failed to ${editingProviderId ? 'update' : 'create'} OIDC provider`)
    },
  })

  const deleteProviderMutation = useMutation({
    mutationFn: (id: string) => api.ssoProviders.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ee-sso-providers'] })
      toast.success('OIDC provider deleted')
    },
    onError: () => {
      toast.error('Failed to delete OIDC provider')
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-heading m-0">Tenants</h3>
          <Button size="sm" onClick={() => {
            setEditingTenantId(null)
            setTenantForm({
              name: '',
              slug: '',
              legacy_partner_key: '',
              partner_aliases: '',
              analyst_ids: [],
              tenant_admin_ids: [],
              is_active: true,
            })
            setShowTenantDialog(true)
          }}>
            <Plus size={14} /> Add Tenant
          </Button>
        </div>
        {tenantsUnavailable ? (
          <EmptyState
            icon={<Building2 size={28} />}
            title="Tenant management unavailable"
            description="The tenant management endpoints are not available in this deployment."
          />
        ) : tenantsLoading ? (
          <CardSkeleton lines={2} />
        ) : tenants && tenants.length > 0 ? (
          <Card>
            {tenants.map((tenant) => (
              <div key={tenant.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
                <Building2 size={14} className="text-muted shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-heading">{tenant.name}</div>
                  <div className="text-[11px] text-muted">
                    {tenant.slug}
                    {tenant.legacy_partner_key ? ` · ${tenant.legacy_partner_key}` : ''}
                    {` · alerts: ${tenant.alert_count} · analysts: ${tenant.analyst_count}`}
                  </div>
                </div>
                <span className={`text-[11px] px-2 py-0.5 rounded ${tenant.is_active ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>
                  {tenant.is_active ? 'Active' : 'Inactive'}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setEditingTenantId(tenant.id)
                    setTenantForm({
                      name: tenant.name,
                      slug: tenant.slug,
                      legacy_partner_key: tenant.legacy_partner_key || '',
                      partner_aliases: Array.isArray((tenant.config as Record<string, unknown>).partner_aliases)
                        ? ((tenant.config as Record<string, unknown>).partner_aliases as string[]).join(', ')
                        : '',
                      analyst_ids: [],
                      tenant_admin_ids: [],
                      is_active: tenant.is_active,
                    })
                    setShowTenantDialog(true)
                  }}
                >
                  Edit
                </Button>
                <button
                  onClick={() => deleteTenantMutation.mutate(tenant.id)}
                  className="p-1.5 rounded hover:bg-danger/10 text-muted hover:text-danger bg-transparent border-none cursor-pointer"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState icon={<Building2 size={28} />} title="No tenants" description="Create a tenant to assign memberships and scope enterprise access" />
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-heading m-0">OIDC Providers</h3>
          <Button size="sm" onClick={() => {
            setEditingProviderId(null)
            setProviderForm({
              name: '',
              issuer: '',
              client_id: '',
              client_secret: '',
              authorize_url: '',
              token_url: '',
              userinfo_url: '',
              jwks_uri: '',
              scope: 'openid profile email',
              enabled: true,
              extra_config: '{}',
            })
            setShowProviderDialog(true)
          }}>
            <Plus size={14} /> Add Provider
          </Button>
        </div>
        {providersQuery.isError ? (
          <EmptyState
            icon={<Shield size={28} />}
            title="OIDC provider management unavailable"
            description="The provider management endpoints are not available in this deployment."
          />
        ) : providersQuery.isLoading ? (
          <CardSkeleton lines={2} />
        ) : providersQuery.data && providersQuery.data.length > 0 ? (
          <Card>
            {providersQuery.data.map((provider) => (
              <div key={provider.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
                <Shield size={14} className="text-muted shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-heading">{provider.name}</div>
                  <div className="text-[11px] text-muted">{provider.issuer}</div>
                </div>
                <span className={`text-[11px] px-2 py-0.5 rounded ${provider.enabled ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>
                  {provider.enabled ? 'Enabled' : 'Disabled'}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setEditingProviderId(provider.id)
                    setProviderForm({
                      name: provider.name,
                      issuer: provider.issuer,
                      client_id: provider.client_id,
                      client_secret: '',
                      authorize_url: provider.authorize_url,
                      token_url: provider.token_url,
                      userinfo_url: provider.userinfo_url || '',
                      jwks_uri: provider.jwks_uri || '',
                      scope: provider.scope,
                      enabled: provider.enabled,
                      extra_config: JSON.stringify(provider.extra_config || {}, null, 2),
                    })
                    setShowProviderDialog(true)
                  }}
                >
                  Edit
                </Button>
                <button
                  onClick={() => deleteProviderMutation.mutate(provider.id)}
                  className="p-1.5 rounded hover:bg-danger/10 text-muted hover:text-danger bg-transparent border-none cursor-pointer"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState icon={<Shield size={28} />} title="No OIDC providers" description="Create a provider to enable enterprise sign-in" />
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-heading m-0">Scoped API Keys</h3>
        </div>
        {keysLoading ? (
          <CardSkeleton lines={2} />
        ) : keys && keys.length > 0 ? (
          <Card>
            {keys.map((k) => (
              <div key={k.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
                <Key size={14} className="text-muted shrink-0" />
                <div className="flex-1">
                  <div className="text-sm text-heading">{k.name}</div>
                  <div className="text-[11px] text-muted font-mono">{k.prefix}...</div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    setSelectedKeyId(k.id)
                    setShowScopeDialog(true)
                  }}
                >
                  Manage Scope
                </Button>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState icon={<Key size={28} />} title="No API keys" description="Create an API key before assigning scopes" />
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-heading m-0">Report Schedules</h3>
          <Button size="sm" onClick={() => setShowScheduleDialog(true)}>
            <Plus size={14} /> Add Schedule
          </Button>
        </div>

        {enterpriseUnavailable ? (
          <EmptyState
            icon={<CalendarDays size={28} />}
            title="Enterprise reporting unavailable"
            description="The report schedule endpoints are not available in this deployment."
          />
        ) : schedulesQuery.isLoading || tenantsLoading ? (
          <CardSkeleton lines={2} />
        ) : schedulesQuery.data && schedulesQuery.data.length > 0 ? (
          <Card>
            {schedulesQuery.data.map((schedule) => (
              <div key={schedule.id} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0">
                <CalendarDays size={14} className="text-muted shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-heading">{schedule.report_type} · {schedule.format}</div>
                  <div className="text-[11px] text-muted">
                    {schedule.cadence}
                    {schedule.destination_email ? ` · ${schedule.destination_email}` : ''}
                    {schedule.last_run_status ? ` · last: ${schedule.last_run_status}` : ''}
                  </div>
                </div>
                <button
                  onClick={() => runScheduleMutation.mutate(schedule.id)}
                  className="p-1.5 rounded hover:bg-surface text-muted hover:text-heading bg-transparent border-none cursor-pointer disabled:opacity-50"
                  title="Run now"
                >
                  {runScheduleMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                </button>
                <button
                  onClick={() => deleteScheduleMutation.mutate(schedule.id)}
                  className="p-1.5 rounded hover:bg-danger/10 text-muted hover:text-danger bg-transparent border-none cursor-pointer"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState icon={<CalendarDays size={28} />} title="No schedules" description="Create a report schedule to automate exports" />
        )}
      </div>

      <Dialog open={showScopeDialog} onClose={() => setShowScopeDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowScopeDialog(false)}>
            <DialogTitle>Manage Key Scope</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            {scopeQuery.isError ? (
              <div className="text-sm text-muted">Scoped key management is not available in this deployment.</div>
            ) : (
              <>
                <div>
                  <Label htmlFor="enterprise-scope-scopes">Scopes</Label>
                  <Input
                    id="enterprise-scope-scopes"
                    value={scopeText || (scopeQuery.data?.scopes.join(', ') ?? '')}
                    onChange={(e) => setScopeText(e.target.value)}
                    placeholder="webhooks:ingest, webhooks:ingest:elastic"
                  />
                </div>
                <div>
                  <Label htmlFor="enterprise-scope-tenant">Tenant</Label>
                  <Select
                    id="enterprise-scope-tenant"
                    value={scopeTenantId || scopeQuery.data?.tenant_id || ''}
                    onChange={(v) => setScopeTenantId(v)}
                    options={[
                      { value: '', label: 'Unowned / global' },
                      ...((tenants || []).map((tenant) => ({
                        value: tenant.id,
                        label: tenant.name,
                      }))),
                    ]}
                    className="w-full"
                  />
                </div>
              </>
            )}
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowScopeDialog(false)}>Close</Button>
            {!scopeQuery.isError && (
              <Button size="sm" variant="primary" onClick={() => updateScopesMutation.mutate()}>
                Save
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showTenantDialog} onClose={() => setShowTenantDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowTenantDialog(false)}>
            <DialogTitle>{editingTenantId ? 'Edit Tenant' : 'Create Tenant'}</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="tenant-name">Name</Label>
                <Input id="tenant-name" value={tenantForm.name} onChange={(e) => setTenantForm({ ...tenantForm, name: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="tenant-slug">Slug</Label>
                <Input id="tenant-slug" value={tenantForm.slug} onChange={(e) => setTenantForm({ ...tenantForm, slug: e.target.value })} />
              </div>
            </div>
            <div>
              <Label htmlFor="tenant-legacy-partner-key">Legacy Partner Key</Label>
              <Input
                id="tenant-legacy-partner-key"
                value={tenantForm.legacy_partner_key}
                onChange={(e) => setTenantForm({ ...tenantForm, legacy_partner_key: e.target.value })}
                placeholder="acme-corp"
              />
            </div>
            <div>
              <Label htmlFor="tenant-partner-aliases">Partner Aliases</Label>
              <Input
                id="tenant-partner-aliases"
                value={tenantForm.partner_aliases}
                onChange={(e) => setTenantForm({ ...tenantForm, partner_aliases: e.target.value })}
                placeholder="alias-one, alias-two"
              />
            </div>
            <div>
              <Label>Members</Label>
              <div className="space-y-2 max-h-32 overflow-y-auto border border-border rounded-md p-3">
                {(analysts || []).map((analyst) => (
                  <label key={analyst.id} className="flex items-center gap-2 text-xs text-text">
                    <input
                      type="checkbox"
                      checked={tenantForm.analyst_ids.includes(analyst.id)}
                      onChange={(e) => setTenantForm({
                        ...tenantForm,
                        analyst_ids: e.target.checked
                          ? [...tenantForm.analyst_ids, analyst.id]
                          : tenantForm.analyst_ids.filter((id) => id !== analyst.id),
                      })}
                    />
                    {analyst.display_name}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <Label>Tenant Admins</Label>
              <div className="space-y-2 max-h-32 overflow-y-auto border border-border rounded-md p-3">
                {(analysts || []).map((analyst) => (
                  <label key={analyst.id} className="flex items-center gap-2 text-xs text-text">
                    <input
                      type="checkbox"
                      checked={tenantForm.tenant_admin_ids.includes(analyst.id)}
                      onChange={(e) => setTenantForm({
                        ...tenantForm,
                        tenant_admin_ids: e.target.checked
                          ? [...tenantForm.tenant_admin_ids, analyst.id]
                          : tenantForm.tenant_admin_ids.filter((id) => id !== analyst.id),
                      })}
                    />
                    {analyst.display_name}
                  </label>
                ))}
              </div>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowTenantDialog(false)}>Cancel</Button>
            <Button size="sm" variant="primary" onClick={() => createTenantMutation.mutate()}>
              {editingTenantId ? 'Save' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showProviderDialog} onClose={() => setShowProviderDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowProviderDialog(false)}>
            <DialogTitle>{editingProviderId ? 'Edit OIDC Provider' : 'Create OIDC Provider'}</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="provider-name">Name</Label>
                <Input id="provider-name" value={providerForm.name} onChange={(e) => setProviderForm({ ...providerForm, name: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="provider-issuer">Issuer</Label>
                <Input id="provider-issuer" value={providerForm.issuer} onChange={(e) => setProviderForm({ ...providerForm, issuer: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="provider-client-id">Client ID</Label>
                <Input id="provider-client-id" value={providerForm.client_id} onChange={(e) => setProviderForm({ ...providerForm, client_id: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="provider-client-secret">Client Secret</Label>
                <Input
                  id="provider-client-secret"
                  type="password"
                  value={providerForm.client_secret}
                  onChange={(e) => setProviderForm({ ...providerForm, client_secret: e.target.value })}
                  placeholder={editingProviderId ? 'Leave blank to keep current' : ''}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="provider-authorize-url">Authorize URL</Label>
                <Input id="provider-authorize-url" value={providerForm.authorize_url} onChange={(e) => setProviderForm({ ...providerForm, authorize_url: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="provider-token-url">Token URL</Label>
                <Input id="provider-token-url" value={providerForm.token_url} onChange={(e) => setProviderForm({ ...providerForm, token_url: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="provider-userinfo-url">Userinfo URL</Label>
                <Input id="provider-userinfo-url" value={providerForm.userinfo_url} onChange={(e) => setProviderForm({ ...providerForm, userinfo_url: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="provider-jwks-uri">JWKS URI</Label>
                <Input id="provider-jwks-uri" value={providerForm.jwks_uri} onChange={(e) => setProviderForm({ ...providerForm, jwks_uri: e.target.value })} />
              </div>
            </div>
            <div>
              <Label htmlFor="provider-scope">Scope</Label>
              <Input id="provider-scope" value={providerForm.scope} onChange={(e) => setProviderForm({ ...providerForm, scope: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="provider-extra-config">Extra Config (JSON)</Label>
              <Textarea
                id="provider-extra-config"
                value={providerForm.extra_config}
                onChange={(e) => setProviderForm({ ...providerForm, extra_config: e.target.value })}
                rows={4}
                className="font-mono"
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowProviderDialog(false)}>Cancel</Button>
            <Button size="sm" variant="primary" onClick={() => createProviderMutation.mutate()}>
              {editingProviderId ? 'Save' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showScheduleDialog} onClose={() => setShowScheduleDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowScheduleDialog(false)}>
            <DialogTitle>Create Report Schedule</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="schedule-report-type">Report Type</Label>
                <Select
                  id="schedule-report-type"
                  value={scheduleForm.report_type}
                  onChange={(v) => setScheduleForm({ ...scheduleForm, report_type: v })}
                  options={[
                    { value: 'audit_log', label: 'Audit Log' },
                    { value: 'sla_compliance', label: 'SLA Compliance' },
                  ]}
                  className="w-full"
                />
              </div>
              <div>
                <Label htmlFor="schedule-format">Format</Label>
                <Select
                  id="schedule-format"
                  value={scheduleForm.format}
                  onChange={(v) => setScheduleForm({ ...scheduleForm, format: v })}
                  options={[
                    { value: 'pdf', label: 'PDF' },
                    { value: 'json', label: 'JSON' },
                    { value: 'csv', label: 'CSV' },
                  ]}
                  className="w-full"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="schedule-cadence">Cadence</Label>
                <Select
                  id="schedule-cadence"
                  value={scheduleForm.cadence}
                  onChange={(v) => setScheduleForm({ ...scheduleForm, cadence: v })}
                  options={[
                    { value: 'manual', label: 'Manual' },
                    { value: 'daily', label: 'Daily' },
                    { value: 'weekly', label: 'Weekly' },
                  ]}
                  className="w-full"
                />
              </div>
              <div>
                <Label htmlFor="schedule-tenant">Tenant</Label>
                <Select
                  id="schedule-tenant"
                  value={scheduleForm.tenant_id}
                  onChange={(v) => setScheduleForm({ ...scheduleForm, tenant_id: v })}
                  options={[
                    { value: '', label: 'Global / none' },
                    ...((tenants || []).map((tenant) => ({
                      value: tenant.id,
                      label: tenant.name,
                    }))),
                  ]}
                  className="w-full"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="schedule-destination-email">Destination Email</Label>
              <Input
                id="schedule-destination-email"
                value={scheduleForm.destination_email}
                onChange={(e) => setScheduleForm({ ...scheduleForm, destination_email: e.target.value })}
                placeholder="soc@example.com"
              />
            </div>
            <div>
              <Label htmlFor="schedule-config">Config (JSON)</Label>
              <Textarea
                id="schedule-config"
                value={scheduleForm.config}
                onChange={(e) => setScheduleForm({ ...scheduleForm, config: e.target.value })}
                rows={3}
                className="font-mono"
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowScheduleDialog(false)}>Cancel</Button>
            <Button size="sm" variant="primary" onClick={() => createScheduleMutation.mutate()}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function SettingsPage() {
  const { analyst } = useAuth()
  const [tab, setTab] = useState<Tab>('integrations')

  if (analyst?.role !== 'admin') {
    return (
      <PageTransition>
        <div className="text-center py-20">
          <Shield size={32} className="text-muted mx-auto mb-3" />
          <div className="text-sm text-muted">Admin access required</div>
        </div>
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageHeader icon={<Settings size={18} />} title="Settings" />

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as Tab)}
        tabs={[
          { value: 'integrations', label: 'Integrations', icon: <Plug size={14} /> },
          { value: 'api-keys', label: 'API Keys', icon: <Key size={14} /> },
          { value: 'analysts', label: 'Analysts', icon: <Users size={14} /> },
          { value: 'enterprise', label: 'Enterprise', icon: <CalendarDays size={14} /> },
        ]}
        className="mb-6"
      />

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.15, ease }}
        >
          {tab === 'integrations' && <IntegrationsTab />}
          {tab === 'api-keys' && <ApiKeysTab />}
          {tab === 'analysts' && <AnalystsTab />}
          {tab === 'enterprise' && <EnterpriseTab />}
        </motion.div>
      </AnimatePresence>
    </PageTransition>
  )
}
