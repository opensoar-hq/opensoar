import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BookOpen, ToggleLeft, ToggleRight, Zap, Play } from 'lucide-react'
import { api, type Playbook } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Card, CardContent } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { PageTransition, StaggerParent, StaggerChild } from '@/components/ui/PageTransition'
import { useToast } from '@/components/ui/Toast'
import { Select } from '@/components/ui/Select'
import { useAuth } from '@/contexts/AuthContext'

function PlaybookCard({
  playbook,
  ownerOptions,
  canManageOwnership,
}: {
  playbook: Playbook
  ownerOptions: { value: string; label: string }[]
  canManageOwnership: boolean
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [showTrigger, setShowTrigger] = useState(false)
  const [alertId, setAlertId] = useState('')

  const toggleMutation = useMutation({
    mutationFn: () => api.playbooks.update(playbook.id, { enabled: !playbook.enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playbooks'] }),
  })

  const runMutation = useMutation({
    mutationFn: () => api.playbooks.run(playbook.id, alertId ? { alert_id: alertId } : undefined),
    onSuccess: () => {
      setShowTrigger(false)
      toast.success('Playbook triggered', `${playbook.name} is now running`)
    },
    onError: () => {
      toast.error('Failed to trigger playbook', `Could not start ${playbook.name}`)
    },
  })

  const ownershipMutation = useMutation({
    mutationFn: (partner: string) => api.playbooks.update(playbook.id, { partner: partner || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      queryClient.invalidateQueries({ queryKey: ['ee-global-resources'] })
      toast.success('Playbook ownership updated')
    },
    onError: () => {
      toast.error('Failed to update playbook ownership')
    },
  })

  return (
    <Card>
      <CardContent>
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-heading">{playbook.name}</span>
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-surface-hover text-muted">
                #{playbook.execution_order}
              </span>
              {playbook.trigger_type && (
                <span className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-accent/15 text-accent">
                  <Zap size={10} /> {playbook.trigger_type}
                </span>
              )}
              <span className="text-[11px] text-muted">v{playbook.version}</span>
            </div>

            {playbook.description && (
              <p className="text-xs text-text mb-2 m-0">{playbook.description}</p>
            )}

            <div className="flex gap-4 text-[11px] text-muted">
              <span>Module: <code className="text-[11px] px-1 py-0.5 bg-bg rounded text-heading">{playbook.module_path}</code></span>
              <span>Function: <code className="text-[11px] px-1 py-0.5 bg-bg rounded text-heading">{playbook.function_name}</code></span>
            </div>

            <div className="mt-2 text-[11px] text-muted">
              Owner: {playbook.partner || 'Global / unowned'}
            </div>

            <div className="mt-1 text-[11px] text-muted">
              Execution order: {playbook.execution_order}
            </div>

            {canManageOwnership && (
              <div className="mt-2 max-w-xs">
                <label htmlFor={`playbook-owner-${playbook.id}`} className="block text-[11px] text-muted mb-1">
                  Assign owner
                </label>
                <Select
                  id={`playbook-owner-${playbook.id}`}
                  value={playbook.partner || ''}
                  onChange={(value) => ownershipMutation.mutate(value)}
                  options={ownerOptions}
                  className="w-full"
                />
              </div>
            )}

            {playbook.trigger_config && Object.keys(playbook.trigger_config).length > 0 && (
              <div className="mt-2 text-[11px] text-muted">
                Conditions: <code className="text-[11px] px-1 py-0.5 bg-bg rounded text-heading">{JSON.stringify(playbook.trigger_config)}</code>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 ml-4">
            <Button variant="ghost" size="sm" onClick={() => setShowTrigger(!showTrigger)}>
              <Play size={14} /> Run
            </Button>
            <button
              onClick={() => toggleMutation.mutate()}
              className="border-none bg-transparent cursor-pointer p-1"
              style={{ color: playbook.enabled ? 'var(--color-success)' : 'var(--color-muted)' }}
              title={playbook.enabled ? 'Disable' : 'Enable'}
            >
              {playbook.enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
            </button>
          </div>
        </div>

        {showTrigger && (
          <div className="mt-3 pt-3 border-t border-border flex items-center gap-2">
            <Input
              type="text"
              placeholder="Alert ID (optional)"
              value={alertId}
              onChange={(e) => setAlertId(e.target.value)}
              className="flex-1 text-xs py-1.5"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
            >
              {runMutation.isPending ? <Spinner size={12} /> : <Play size={12} />}
              Execute
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function PlaybooksListPage() {
  const { analyst } = useAuth()
  const { data: playbooks, isLoading } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => api.playbooks.list(),
  })
  const { data: tenants = [] } = useQuery({
    queryKey: ['playbook-owner-tenants'],
    queryFn: api.tenants.list,
    enabled: analyst?.role === 'admin',
    retry: false,
  })
  const ownerOptions = [
    { value: '', label: 'Global / unowned' },
    ...tenants.map((tenant) => ({
      value: tenant.legacy_partner_key || tenant.slug,
      label: tenant.name,
    })),
  ]

  if (isLoading) {
    return (
      <div>
        <PageHeader icon={<BookOpen size={18} />} title="Playbooks" />
        <div className="grid gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <CardSkeleton key={i} lines={2} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <PageTransition>
      <PageHeader icon={<BookOpen size={18} />} title="Playbooks" count={playbooks?.length} />

      {(!playbooks || playbooks.length === 0) && (
        <EmptyState icon={<BookOpen size={32} />} title="No playbooks" description="Add playbooks to the playbooks directory" />
      )}

      {playbooks && playbooks.length > 0 && (
        <StaggerParent className="grid gap-3">
          {playbooks.map((pb) => (
            <StaggerChild key={pb.id}>
              <PlaybookCard
                playbook={pb}
                ownerOptions={ownerOptions}
                canManageOwnership={analyst?.role === 'admin'}
              />
            </StaggerChild>
          ))}
        </StaggerParent>
      )}
    </PageTransition>
  )
}
