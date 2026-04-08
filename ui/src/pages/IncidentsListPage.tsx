import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Briefcase, Clock, UserCheck, Plus, Link2, Globe } from 'lucide-react'
import { api, type IncidentSuggestion } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { Input, Textarea, Label } from '@/components/ui/Input'
import { Table, TableHeader, TableBody, TableHead, TableCell, TableHeaderRow } from '@/components/ui/Table'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState } from '@/components/ui/EmptyState'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/Dialog'
import { PageTransition } from '@/components/ui/PageTransition'
import { useToast } from '@/components/ui/Toast'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { cn, timeAgo } from '@/lib/utils'

function CreateIncidentDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({
    title: '',
    severity: 'medium',
    description: '',
  })

  const createMutation = useMutation({
    mutationFn: () =>
      api.incidents.create({
        title: form.title,
        severity: form.severity,
        description: form.description || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      toast.success('Incident created')
      onClose()
      setForm({ title: '', severity: 'medium', description: '' })
    },
    onError: (err) => {
      toast.error('Failed to create incident', err instanceof Error ? err.message : 'Unknown error')
    },
  })

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogContent>
        <DialogHeader onClose={onClose}>
          <DialogTitle>Create Incident</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <div>
            <Label>Title</Label>
            <Input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Incident title"
            />
          </div>
          <div>
            <Label>Severity</Label>
            <Select
              value={form.severity}
              onChange={(v) => setForm({ ...form, severity: v })}
              options={[
                { value: 'critical', label: 'Critical' },
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low', label: 'Low' },
              ]}
              className="w-full"
            />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Brief description of the incident..."
              rows={3}
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => createMutation.mutate()}
            disabled={!form.title || createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating...' : 'Create Incident'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function IncidentsListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { selectedTenantId } = useWorkspace()
  const [filters, setFilters] = useState<{ severity?: string; status?: string }>({})
  const [page, setPage] = useState(0)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const limit = 50

  const { data, isLoading } = useQuery({
    queryKey: ['incidents', filters, page, selectedTenantId],
    queryFn: () => api.incidents.list({ ...filters, tenant_id: selectedTenantId || undefined, limit, offset: page * limit }),
  })

  const { data: suggestions, isLoading: suggestionsLoading } = useQuery({
    queryKey: ['incident-suggestions', selectedTenantId],
    queryFn: () => api.incidents.suggestions(),
  })

  const suggestionMutation = useMutation({
    mutationFn: async (suggestion: IncidentSuggestion) => {
      const incident = await api.incidents.create({
        title: `Correlated activity from ${suggestion.source_ip}`,
        severity: 'high',
        description: `Suggested incident created from ${suggestion.alert_count} unlinked alerts sharing source IP ${suggestion.source_ip}.`,
      })

      for (const alert of suggestion.alerts) {
        await api.incidents.linkAlert(incident.id, alert.id)
      }

      return incident
    },
    onSuccess: (incident) => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      queryClient.invalidateQueries({ queryKey: ['incident-suggestions'] })
      toast.success(`Created ${incident.title}`)
      navigate(`/incidents/${incident.id}`)
    },
    onError: () => toast.error('Failed to create incident from suggestion'),
  })

  const incidents = data?.incidents ?? []
  const groupedSuggestions = suggestions ?? []

  return (
    <PageTransition>
      <PageHeader icon={<Briefcase size={18} />} title="Incidents" count={data?.total}>
        <div className="flex items-center gap-2">
          <Select
            value={filters.severity || ''}
            onChange={(v) => { setFilters((f) => ({ ...f, severity: v || undefined })); setPage(0) }}
            options={[
              { value: '', label: 'All severities' },
              { value: 'critical', label: 'Critical' },
              { value: 'high', label: 'High' },
              { value: 'medium', label: 'Medium' },
              { value: 'low', label: 'Low' },
            ]}
          />
          <Select
            value={filters.status || ''}
            onChange={(v) => { setFilters((f) => ({ ...f, status: v || undefined })); setPage(0) }}
            options={[
              { value: '', label: 'All statuses' },
              { value: 'open', label: 'Open' },
              { value: 'investigating', label: 'Investigating' },
              { value: 'contained', label: 'Contained' },
              { value: 'closed', label: 'Closed' },
            ]}
          />
          <Button size="sm" variant="primary" onClick={() => setShowCreateDialog(true)}>
            <Plus size={14} /> Create
          </Button>
        </div>
      </PageHeader>

      {!suggestionsLoading && groupedSuggestions.length > 0 && (
        <div className="mb-4 rounded-lg border border-border bg-surface px-4 py-3">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <div className="text-sm font-semibold text-heading">Correlation Suggestions</div>
              <div className="text-xs text-muted">Unlinked alert groups that likely belong in the same incident.</div>
            </div>
          </div>
          <div className="space-y-2">
            {groupedSuggestions.map((suggestion) => (
              <div
                key={suggestion.source_ip}
                className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm text-heading font-medium">
                    <Globe size={13} className="text-accent" />
                    <span className="font-mono">{suggestion.source_ip}</span>
                  </div>
                  <div className="text-xs text-muted mt-1">
                    {suggestion.alert_count} unlinked alert{suggestion.alert_count !== 1 ? 's' : ''}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {suggestion.alerts.slice(0, 3).map((alert) => (
                      <button
                        key={alert.id}
                        onClick={() => navigate(`/alerts/${alert.id}`)}
                        className={cn(
                          'px-2 py-1 rounded-md text-[11px] text-left',
                          'bg-bg border border-border hover:border-accent/40 hover:bg-surface-hover',
                          'cursor-pointer transition-colors',
                        )}
                      >
                        {alert.title}
                      </button>
                    ))}
                    {suggestion.alerts.length > 3 && (
                      <span className="px-2 py-1 text-[11px] text-muted">+{suggestion.alerts.length - 3} more</span>
                    )}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => suggestionMutation.mutate(suggestion)}
                  disabled={suggestionMutation.isPending}
                >
                  <Link2 size={13} /> Create Incident
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {isLoading && <TableSkeleton rows={8} cols={6} />}

      {!isLoading && incidents.length === 0 && (
        <EmptyState
          icon={<Briefcase size={32} />}
          title="No incidents found"
          description="Adjust your filters or create an incident to get started"
        />
      )}

      {!isLoading && incidents.length > 0 && (
        <div>
          <Table>
            <TableHeader>
              <TableHeaderRow>
                <TableHead>Title</TableHead>
                <TableHead className="w-24">Severity</TableHead>
                <TableHead className="w-28">Status</TableHead>
                <TableHead className="w-20">Alerts</TableHead>
                <TableHead className="w-28">Assignee</TableHead>
                <TableHead className="w-24">Time</TableHead>
              </TableHeaderRow>
            </TableHeader>
            <TableBody>
              {incidents.map((incident) => (
                <tr
                  key={incident.id}
                  onClick={() => navigate(`/incidents/${incident.id}`)}
                  className="border-b border-border transition-colors group cursor-pointer hover:bg-surface-hover"
                >
                  <TableCell>
                    <span className="text-heading group-hover:text-accent transition-colors">
                      {incident.title}
                    </span>
                  </TableCell>
                  <TableCell>
                    <SeverityBadge severity={incident.severity} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={incident.status} />
                  </TableCell>
                  <TableCell className="text-xs text-muted">
                    {incident.alert_count}
                  </TableCell>
                  <TableCell className="text-xs text-muted">
                    {incident.assigned_username ? (
                      <span className="flex items-center gap-1">
                        <UserCheck size={11} className="text-accent" />
                        {incident.assigned_username}
                      </span>
                    ) : '—'}
                  </TableCell>
                  <TableCell className="text-xs text-muted whitespace-nowrap">
                    <Clock size={11} className="inline mr-1 align-[-1px]" />
                    {timeAgo(incident.created_at)}
                  </TableCell>
                </tr>
              ))}
            </TableBody>
          </Table>

          {data && (
            <Pagination
              page={page}
              total={data.total}
              limit={limit}
              onPageChange={setPage}
            />
          )}
        </div>
      )}

      <CreateIncidentDialog open={showCreateDialog} onClose={() => setShowCreateDialog(false)} />
    </PageTransition>
  )
}
