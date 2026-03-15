import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Briefcase, Clock, Link2, Unlink, Shield } from 'lucide-react'
import { api, type Alert } from '@/api'
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Label } from '@/components/ui/Input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Table, TableHeader, TableBody, TableHead, TableCell, TableHeaderRow } from '@/components/ui/Table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/Dialog'
import { Tooltip } from '@/components/ui/Tooltip'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { useToast } from '@/components/ui/Toast'
import { PageTransition, StaggerParent, StaggerChild } from '@/components/ui/PageTransition'
import { cn, timeAgo, formatDate } from '@/lib/utils'

export function IncidentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [showLinkDialog, setShowLinkDialog] = useState(false)
  const [linkAlertId, setLinkAlertId] = useState('')

  const { data: incident, isLoading } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => api.incidents.get(id!),
    enabled: !!id,
  })

  const { data: linkedAlerts } = useQuery({
    queryKey: ['incident-alerts', id],
    queryFn: () => api.incidents.alerts(id!),
    enabled: !!id,
  })

  const invalidateIncident = () => {
    queryClient.invalidateQueries({ queryKey: ['incident', id] })
    queryClient.invalidateQueries({ queryKey: ['incident-alerts', id] })
    queryClient.invalidateQueries({ queryKey: ['incidents'] })
  }

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.incidents.update(id!, data),
    onSuccess: () => {
      invalidateIncident()
      toast.success('Incident updated')
    },
    onError: () => toast.error('Failed to update incident'),
  })

  const linkMutation = useMutation({
    mutationFn: (alertId: string) => api.incidents.linkAlert(id!, alertId),
    onSuccess: () => {
      invalidateIncident()
      toast.success('Alert linked')
      setShowLinkDialog(false)
      setLinkAlertId('')
    },
    onError: () => toast.error('Failed to link alert'),
  })

  const unlinkMutation = useMutation({
    mutationFn: (alertId: string) => api.incidents.unlinkAlert(id!, alertId),
    onSuccess: () => {
      invalidateIncident()
      toast.success('Alert unlinked')
    },
    onError: () => toast.error('Failed to unlink alert'),
  })

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-4xl">
        <CardSkeleton lines={3} />
        <CardSkeleton lines={4} />
      </div>
    )
  }

  if (!incident) return <div className="text-center py-20 text-muted">Incident not found</div>

  const isClosed = incident.status === 'closed'

  return (
    <PageTransition>
      <Link to="/incidents" className="inline-flex items-center gap-1 text-xs text-muted hover:text-heading no-underline mb-4">
        <ArrowLeft size={14} /> Incidents
      </Link>

      <StaggerParent className="space-y-4 max-w-4xl">
        {/* Header Card */}
        <StaggerChild>
          <Card>
            <CardContent>
              <div className="flex items-start gap-4 mb-3">
                <h1 className="text-base font-semibold text-heading m-0 flex-1 min-w-0 leading-snug">
                  {incident.title}
                </h1>
                <div className="flex items-center gap-1.5 shrink-0">
                  {isClosed ? (
                    <Button
                      size="sm"
                      onClick={() => updateMutation.mutate({ status: 'open' })}
                      disabled={updateMutation.isPending}
                    >
                      Reopen
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => updateMutation.mutate({ status: 'closed' })}
                      disabled={updateMutation.isPending}
                    >
                      Close
                    </Button>
                  )}
                </div>
              </div>

              {incident.description && (
                <p className="text-sm text-text m-0 mb-3">{incident.description}</p>
              )}

              <div className="flex items-center gap-2 flex-wrap">
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />
                {incident.assigned_username && (
                  <span className="flex items-center gap-1 text-[11px] text-accent">
                    {incident.assigned_username}
                  </span>
                )}
                {incident.tags && incident.tags.length > 0 && incident.tags.map((t) => (
                  <span key={t} className="px-2 py-0.5 text-[11px] bg-bg border border-border rounded text-heading">{t}</span>
                ))}
                <span className="text-border">|</span>
                <Tooltip content={formatDate(incident.created_at)}>
                  <span className="text-[11px] text-muted flex items-center gap-1">
                    <Clock size={10} /> {timeAgo(incident.created_at)}
                  </span>
                </Tooltip>
                <span className="text-[11px] text-muted">
                  {incident.alert_count} alert{incident.alert_count !== 1 ? 's' : ''}
                </span>
              </div>
            </CardContent>
          </Card>
        </StaggerChild>

        {/* Linked Alerts */}
        <StaggerChild>
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>Linked Alerts</CardTitle>
              <Button size="sm" onClick={() => setShowLinkDialog(true)}>
                <Link2 size={13} /> Link Alert
              </Button>
            </CardHeader>
            <CardContent>
              {(!linkedAlerts || linkedAlerts.length === 0) ? (
                <EmptyState
                  icon={<Shield size={24} />}
                  title="No linked alerts"
                  description="Link alerts to this incident to track related events"
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableHeaderRow>
                      <TableHead>Title</TableHead>
                      <TableHead className="w-24">Severity</TableHead>
                      <TableHead className="w-28">Status</TableHead>
                      <TableHead className="w-24">Time</TableHead>
                      <TableHead className="w-16"></TableHead>
                    </TableHeaderRow>
                  </TableHeader>
                  <TableBody>
                    {linkedAlerts.map((alert: Alert) => (
                      <tr
                        key={alert.id}
                        className="border-b border-border transition-colors group cursor-pointer hover:bg-surface-hover"
                        onClick={() => navigate(`/alerts/${alert.id}`)}
                      >
                        <TableCell>
                          <span className="text-heading group-hover:text-accent transition-colors">
                            {alert.title}
                          </span>
                        </TableCell>
                        <TableCell>
                          <SeverityBadge severity={alert.severity} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={alert.status} />
                        </TableCell>
                        <TableCell className="text-xs text-muted whitespace-nowrap">
                          <Clock size={11} className="inline mr-1 align-[-1px]" />
                          {timeAgo(alert.created_at)}
                        </TableCell>
                        <TableCell>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              unlinkMutation.mutate(alert.id)
                            }}
                            className="p-1.5 rounded-md hover:bg-surface-hover text-muted hover:text-danger bg-transparent border-none cursor-pointer transition-colors opacity-0 group-hover:opacity-100"
                            title="Unlink alert"
                          >
                            <Unlink size={13} />
                          </button>
                        </TableCell>
                      </tr>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </StaggerChild>

        {/* Info Card */}
        <StaggerChild>
          <Card>
            <CardHeader>
              <CardTitle>Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-muted uppercase tracking-wide">Created</span>
                <span className="text-xs text-heading">{formatDate(incident.created_at)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-muted uppercase tracking-wide">Updated</span>
                <span className="text-xs text-heading">{formatDate(incident.updated_at)}</span>
              </div>
              {incident.closed_at && (
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-muted uppercase tracking-wide">Closed</span>
                  <span className="text-xs text-heading">{formatDate(incident.closed_at)}</span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-muted uppercase tracking-wide">ID</span>
                <span className="text-xs text-heading font-mono">{incident.id.slice(0, 8)}</span>
              </div>
            </CardContent>
          </Card>
        </StaggerChild>
      </StaggerParent>

      {/* Link Alert Dialog */}
      <Dialog open={showLinkDialog} onClose={() => setShowLinkDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowLinkDialog(false)}>
            <DialogTitle>Link Alert</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <div>
              <Label>Alert ID</Label>
              <Input
                value={linkAlertId}
                onChange={(e) => setLinkAlertId(e.target.value)}
                placeholder="Paste alert ID..."
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setShowLinkDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => linkMutation.mutate(linkAlertId.trim())}
              disabled={!linkAlertId.trim() || linkMutation.isPending}
            >
              {linkMutation.isPending ? 'Linking...' : 'Link Alert'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageTransition>
  )
}
