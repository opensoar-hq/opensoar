import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Search, Clock, UserCheck, X, Copy, Plus } from 'lucide-react'
import { api } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { Input, Textarea, Label } from '@/components/ui/Input'
import { Table, TableHeader, TableBody, TableHead, TableCell, TableHeaderRow } from '@/components/ui/Table'
import { Checkbox } from '@/components/ui/Checkbox'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState } from '@/components/ui/EmptyState'
import { Tooltip } from '@/components/ui/Tooltip'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/Dialog'
import { PageTransition } from '@/components/ui/PageTransition'
import { useToast } from '@/components/ui/Toast'
import { cn, timeAgo } from '@/lib/utils'

function CreateAlertDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({
    title: '',
    severity: 'medium',
    source: 'manual',
    source_ip: '',
    dest_ip: '',
    hostname: '',
    description: '',
    raw_json: '',
  })

  const createMutation = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        rule_name: form.title,
        severity: form.severity,
        source: form.source,
        description: form.description || undefined,
        source_ip: form.source_ip || undefined,
        dest_ip: form.dest_ip || undefined,
        hostname: form.hostname || undefined,
      }

      if (form.raw_json.trim()) {
        try {
          const custom = JSON.parse(form.raw_json)
          Object.assign(payload, custom)
        } catch {
          throw new Error('Invalid JSON')
        }
      }

      return api.webhooks.createAlert(payload)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success('Alert created', data.message)
      onClose()
      setForm({
        title: '',
        severity: 'medium',
        source: 'manual',
        source_ip: '',
        dest_ip: '',
        hostname: '',
        description: '',
        raw_json: '',
      })
    },
    onError: (err) => {
      toast.error('Failed to create alert', err instanceof Error ? err.message : 'Unknown error')
    },
  })

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogContent>
        <DialogHeader onClose={onClose}>
          <DialogTitle>Create Alert</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <div>
            <Label>Title</Label>
            <Input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Suspicious login from unusual IP"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
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
              <Label>Source</Label>
              <Input
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
                placeholder="manual"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>Source IP</Label>
              <Input
                value={form.source_ip}
                onChange={(e) => setForm({ ...form, source_ip: e.target.value })}
                placeholder="10.0.0.1"
              />
            </div>
            <div>
              <Label>Dest IP</Label>
              <Input
                value={form.dest_ip}
                onChange={(e) => setForm({ ...form, dest_ip: e.target.value })}
                placeholder="192.168.1.1"
              />
            </div>
            <div>
              <Label>Hostname</Label>
              <Input
                value={form.hostname}
                onChange={(e) => setForm({ ...form, hostname: e.target.value })}
                placeholder="web-01"
              />
            </div>
          </div>

          <div>
            <Label>Description</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Brief description of the alert..."
              rows={2}
            />
          </div>

          <div>
            <Label>Additional JSON <span className="font-normal text-muted">(optional)</span></Label>
            <Textarea
              value={form.raw_json}
              onChange={(e) => setForm({ ...form, raw_json: e.target.value })}
              placeholder='{"custom_field": "value", "tags": ["test"]}'
              rows={3}
              className="font-mono text-xs"
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
            {createMutation.isPending ? 'Creating...' : 'Create Alert'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function AlertsListPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [filters, setFilters] = useState<{ severity?: string; status?: string; partner?: string; search?: string }>({})
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const limit = 50

  const selectionActive = selected.size > 0

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', filters, page],
    queryFn: () => api.alerts.list({ ...filters, limit, offset: page * limit }),
  })

  const bulkMutation = useMutation({
    mutationFn: (params: { action: string; resolve_reason?: string; determination?: string; severity?: string }) =>
      api.alerts.bulk({ alert_ids: [...selected], ...params }),
    onSuccess: () => {
      setSelected(new Set())
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
  })

  const filteredAlerts = data?.alerts.filter((a) => {
    if (!filters.search) return true
    const s = filters.search.toLowerCase()
    return a.title.toLowerCase().includes(s)
      || a.source_ip?.toLowerCase().includes(s)
      || a.hostname?.toLowerCase().includes(s)
      || a.rule_name?.toLowerCase().includes(s)
  }) ?? []

  // Derive unique partners for filter dropdown
  const partners = [...new Set((data?.alerts ?? []).map((a) => a.partner).filter(Boolean) as string[])]

  const allSelected = filteredAlerts.length > 0 && filteredAlerts.every((a) => selected.has(a.id))
  const someSelected = filteredAlerts.some((a) => selected.has(a.id)) && !allSelected

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(filteredAlerts.map((a) => a.id)))
    }
  }

  const toggleOne = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  return (
    <PageTransition>
      <PageHeader icon={<Shield size={18} />} title="Alerts" count={data?.total}>
        <div className="flex items-center gap-2">
          <Input
            icon={<Search size={14} />}
            type="text"
            placeholder="Search alerts..."
            value={filters.search || ''}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value || undefined }))}
            className="w-56 !py-1.5 !text-xs"
          />
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
              { value: 'new', label: 'New' },
              { value: 'in_progress', label: 'In Progress' },
              { value: 'resolved', label: 'Resolved' },
            ]}
          />
          {partners.length > 0 && (
            <Select
              value={filters.partner || ''}
              onChange={(v) => { setFilters((f) => ({ ...f, partner: v || undefined })); setPage(0) }}
              options={[
                { value: '', label: 'All partners' },
                ...partners.map((p) => ({ value: p, label: p })),
              ]}
            />
          )}
          <Button size="sm" variant="primary" onClick={() => setShowCreateDialog(true)}>
            <Plus size={14} /> Create
          </Button>
        </div>
      </PageHeader>

      {isLoading && <TableSkeleton rows={8} cols={7} />}

      {!isLoading && filteredAlerts.length === 0 && (
        <EmptyState
          icon={<Shield size={32} />}
          title="No alerts found"
          description="Adjust your filters or create a manual alert to get started"
        />
      )}

      {!isLoading && filteredAlerts.length > 0 && (
        <div className={cn('alerts-table', selectionActive && 'selection-active')}>
          <Table>
            <TableHeader>
              <TableHeaderRow>
                <TableHead className="w-10 checkbox-col">
                  <Checkbox
                    checked={allSelected}
                    indeterminate={someSelected}
                    onChange={toggleAll}
                  />
                </TableHead>
                <TableHead className="w-24">Severity</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="w-[7.5rem]">Status</TableHead>
                <TableHead className="w-24">Source</TableHead>
                <TableHead className="w-32">Source IP</TableHead>
                <TableHead className="w-24">Partner</TableHead>
                <TableHead className="w-24">Assignee</TableHead>
                <TableHead className="w-24">Time</TableHead>
              </TableHeaderRow>
            </TableHeader>
            <TableBody>
              {filteredAlerts.map((alert) => {
                const isSelected = selected.has(alert.id)
                return (
                  <tr
                    key={alert.id}
                    onClick={() => navigate(`/alerts/${alert.id}`)}
                    className={cn(
                      'border-b border-border transition-colors group cursor-pointer',
                      isSelected
                        ? 'bg-accent/[0.06]'
                        : 'hover:bg-surface-hover',
                    )}
                  >
                    <TableCell className="checkbox-col">
                      <Checkbox
                        checked={isSelected}
                        onChange={() => toggleOne(alert.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <SeverityBadge severity={alert.severity} />
                    </TableCell>
                    <TableCell>
                      <span className="text-heading group-hover:text-accent transition-colors">
                        {alert.title}
                      </span>
                      {alert.duplicate_count > 1 && (
                        <Tooltip content={`${alert.duplicate_count} duplicate alerts`}>
                          <span className="ml-1.5 text-[10px] text-warning bg-warning/15 px-1.5 py-0.5 rounded">
                            <Copy size={9} className="inline mr-0.5 align-[-1px]" />
                            {alert.duplicate_count}x
                          </span>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={alert.status} />
                    </TableCell>
                    <TableCell className="text-xs text-muted">{alert.source}</TableCell>
                    <TableCell className="text-xs font-mono text-muted">{alert.source_ip || '—'}</TableCell>
                    <TableCell className="text-xs text-muted">{alert.partner || '—'}</TableCell>
                    <TableCell className="text-xs text-muted">
                      {alert.assigned_username ? (
                        <span className="flex items-center gap-1">
                          <UserCheck size={11} className="text-accent" />
                          {alert.assigned_username}
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell className="text-xs text-muted whitespace-nowrap">
                      <Clock size={11} className="inline mr-1 align-[-1px]" />
                      {timeAgo(alert.created_at)}
                    </TableCell>
                  </tr>
                )
              })}
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

      {/* Bulk action bar — fixed bottom overlay */}
      <AnimatePresence>
        {selectionActive && (
          <motion.div
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-5 py-3 border border-accent/30 rounded-xl bg-surface shadow-2xl shadow-black/40"
          >
            <span className="text-xs text-heading font-medium whitespace-nowrap">
              {selected.size} selected
            </span>
            <div className="w-px h-5 bg-border" />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => bulkMutation.mutate({ action: 'assign' })} disabled={bulkMutation.isPending}>
                <UserCheck size={13} /> Assign to Me
              </Button>
              <Button size="sm" variant="danger" onClick={() => bulkMutation.mutate({ action: 'resolve', determination: 'malicious' })} disabled={bulkMutation.isPending}>
                Resolve
              </Button>
            </div>
            <div className="w-px h-5 bg-border" />
            <button
              onClick={() => setSelected(new Set())}
              className="p-1.5 rounded-md hover:bg-surface-hover text-muted hover:text-heading bg-transparent border-none cursor-pointer transition-colors"
            >
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <CreateAlertDialog open={showCreateDialog} onClose={() => setShowCreateDialog(false)} />
    </PageTransition>
  )
}
