import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Briefcase, Clock, UserCheck, Plus } from 'lucide-react'
import { api } from '@/api'
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
import { timeAgo } from '@/lib/utils'

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
  const { selectedTenantId } = useWorkspace()
  const [filters, setFilters] = useState<{ severity?: string; status?: string }>({})
  const [page, setPage] = useState(0)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const limit = 50

  const { data, isLoading } = useQuery({
    queryKey: ['incidents', filters, page, selectedTenantId],
    queryFn: () => api.incidents.list({ ...filters, tenant_id: selectedTenantId || undefined, limit, offset: page * limit }),
  })

  const incidents = data?.incidents ?? []

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
