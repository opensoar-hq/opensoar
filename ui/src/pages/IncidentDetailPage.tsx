import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Clock, Link2, Unlink, Shield, MessageSquare, Pencil, History, UserCheck, Users, Search } from 'lucide-react'
import { api, type Alert, type Activity, type Analyst, type Observable } from '@/api'
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Label } from '@/components/ui/Input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Select } from '@/components/ui/Select'
import { Table, TableHeader, TableBody, TableHead, TableCell, TableHeaderRow } from '@/components/ui/Table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/Dialog'
import { Tooltip } from '@/components/ui/Tooltip'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { useToast } from '@/components/ui/Toast'
import { PageTransition, StaggerParent, StaggerChild } from '@/components/ui/PageTransition'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import { timeAgo, formatDate } from '@/lib/utils'

const ACTION_LABELS: Record<string, string> = {
  incident_created: 'Incident Created',
  incident_linked: 'Incident Linked',
  status_change: 'Status Changed',
  severity_change: 'Severity Changed',
  assigned: 'Assignment Updated',
  alert_linked: 'Alert Linked',
  alert_unlinked: 'Alert Unlinked',
  observable_added: 'Observable Added',
  comment: 'Comment',
}

const ACTION_COLORS: Record<string, string> = {
  incident_created: 'var(--color-success)',
  incident_linked: 'var(--color-info)',
  status_change: 'var(--color-info)',
  severity_change: 'var(--color-warning)',
  assigned: 'var(--color-info)',
  alert_linked: 'var(--color-info)',
  alert_unlinked: 'var(--color-danger)',
  observable_added: 'var(--color-info)',
  comment: 'var(--color-text)',
}

function IncidentTimelineEntry({
  activity, incidentId, isOwnComment,
}: {
  activity: Activity
  incidentId: string
  isOwnComment: boolean
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(activity.detail || '')
  const [showHistory, setShowHistory] = useState(false)

  const editMutation = useMutation({
    mutationFn: (text: string) => api.incidents.editComment(incidentId, activity.id, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incident-activities', incidentId] })
      setEditing(false)
      toast.success('Comment updated')
    },
    onError: () => toast.error('Failed to edit comment'),
  })

  const isComment = activity.action === 'comment'
  const isEdited = activity.created_at !== activity.updated_at
  const editHistory = (activity.metadata_json?.edit_history as Array<{ text: string; edited_at: string }>) || []

  return (
    <div className="relative pl-6 pb-4 last:pb-0">
      <div
        className={cn(
          'absolute left-0 top-1.5 w-[15px] h-[15px] rounded-full border-2 flex items-center justify-center',
          isComment ? 'border-accent/40 bg-accent/10' : 'border-border bg-surface',
        )}
      >
        {isComment ? (
          <MessageSquare size={7} className="text-accent" />
        ) : (
          <div
            className="w-[7px] h-[7px] rounded-full"
            style={{ backgroundColor: ACTION_COLORS[activity.action] || 'var(--color-muted)' }}
          />
        )}
      </div>
      <div className="text-xs">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={cn('font-medium', isComment ? 'text-accent' : 'text-heading')}>
            {isComment ? (activity.analyst_username || 'System') : (ACTION_LABELS[activity.action] || activity.action)}
          </span>
          <Tooltip content={formatDate(activity.created_at)}>
            <span className="text-muted">{timeAgo(activity.created_at)}</span>
          </Tooltip>
          {isComment && isEdited && (
            <Tooltip content={`Edited ${formatDate(activity.updated_at)}`}>
              <span className="text-muted/60 text-[10px] italic">edited</span>
            </Tooltip>
          )}
        </div>

        {isComment && editing ? (
          <div className="mt-1 space-y-1.5">
            <Input
              type="text"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && editText.trim()) editMutation.mutate(editText.trim())
                if (e.key === 'Escape') setEditing(false)
              }}
              className="!text-xs"
              autoFocus
            />
            <div className="flex gap-1">
              <Button size="sm" variant="primary" onClick={() => editText.trim() && editMutation.mutate(editText.trim())} disabled={editMutation.isPending}>
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : isComment && activity.detail ? (
          <div className="group/comment bg-surface-hover/50 px-3 py-2 rounded-md mt-1 relative">
            <div className="text-text">{activity.detail}</div>
            {isOwnComment && (
              <button
                onClick={() => { setEditText(activity.detail || ''); setEditing(true) }}
                className="absolute top-1.5 right-1.5 p-1 rounded bg-transparent border-none cursor-pointer text-muted hover:text-accent opacity-0 group-hover/comment:opacity-100 transition-opacity"
                title="Edit comment"
              >
                <Pencil size={10} />
              </button>
            )}
            {editHistory.length > 0 && (
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="flex items-center gap-1 mt-1.5 text-[10px] text-muted hover:text-accent bg-transparent border-none cursor-pointer p-0 transition-colors"
              >
                <History size={9} /> {editHistory.length} edit{editHistory.length > 1 ? 's' : ''}
              </button>
            )}
            {showHistory && editHistory.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border space-y-1.5">
                {editHistory.map((entry, i) => (
                  <div key={i} className="text-[10px]">
                    <span className="text-muted">{timeAgo(entry.edited_at)}</span>
                    <div className="text-muted/70 line-through">{entry.text}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : activity.detail ? (
          <div className="text-text">{activity.detail}</div>
        ) : null}

        {!isComment && activity.analyst_username && (
          <div className="text-muted text-[11px] mt-0.5">by {activity.analyst_username}</div>
        )}
      </div>
    </div>
  )
}

export function IncidentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { analyst } = useAuth()
  const toast = useToast()
  const [showLinkDialog, setShowLinkDialog] = useState(false)
  const [showAssignDialog, setShowAssignDialog] = useState(false)
  const [linkAlertId, setLinkAlertId] = useState('')
  const [commentText, setCommentText] = useState('')
  const [observableForm, setObservableForm] = useState({
    type: 'ip',
    value: '',
    source: '',
  })

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

  const { data: activities } = useQuery({
    queryKey: ['incident-activities', id],
    queryFn: () => api.incidents.activities(id!),
    enabled: !!id,
  })

  const { data: observables } = useQuery({
    queryKey: ['incident-observables', id],
    queryFn: () => api.incidents.observables(id!),
    enabled: !!id,
  })

  const { data: analysts } = useQuery({
    queryKey: ['analysts'],
    queryFn: api.analysts.list,
  })

  const invalidateIncident = () => {
    queryClient.invalidateQueries({ queryKey: ['incident', id] })
    queryClient.invalidateQueries({ queryKey: ['incident-alerts', id] })
    queryClient.invalidateQueries({ queryKey: ['incident-activities', id] })
    queryClient.invalidateQueries({ queryKey: ['incident-observables', id] })
    queryClient.invalidateQueries({ queryKey: ['incidents'] })
  }

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.incidents.update(id!, data),
    onSuccess: (_data, variables) => {
      invalidateIncident()
      if (Object.prototype.hasOwnProperty.call(variables, 'assigned_to')) {
        setShowAssignDialog(false)
        toast.success('Incident assignment updated')
      } else {
        toast.success('Incident updated')
      }
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

  const commentMutation = useMutation({
    mutationFn: (text: string) => api.incidents.addComment(id!, text),
    onSuccess: () => {
      setCommentText('')
      queryClient.invalidateQueries({ queryKey: ['incident-activities', id] })
      toast.success('Comment added')
    },
    onError: () => toast.error('Failed to add comment'),
  })

  const observableMutation = useMutation({
    mutationFn: () => api.incidents.createObservable(id!, {
      type: observableForm.type,
      value: observableForm.value.trim(),
      source: observableForm.source.trim() || undefined,
    }),
    onSuccess: () => {
      invalidateIncident()
      setObservableForm({ type: 'ip', value: '', source: '' })
      toast.success('Observable added')
    },
    onError: () => toast.error('Failed to add observable'),
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
  const isUnassigned = !incident.assigned_to
  const isAssignedToMe = analyst && incident.assigned_to === analyst.id
  const otherAnalysts = (analysts || []).filter((a: Analyst) => a.is_active && a.id !== incident.assigned_to)

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
                  {!isClosed && (
                    <>
                      {analyst && isUnassigned && (
                        <Button variant="primary" size="sm" onClick={() => updateMutation.mutate({ assigned_to: analyst.id })} disabled={updateMutation.isPending}>
                          <UserCheck size={13} /> Assign to me
                        </Button>
                      )}
                      {analyst && !isUnassigned && (
                        <Button variant="ghost" size="sm" onClick={() => setShowAssignDialog(true)} disabled={updateMutation.isPending}>
                          <Users size={13} /> {isAssignedToMe ? 'Reassign' : 'Assign'}
                        </Button>
                      )}
                    </>
                  )}
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

        <StaggerChild>
          <Card>
            <CardHeader>
              <CardTitle>Observables</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-[120px_minmax(0,1fr)_160px_auto] gap-2">
                <Select
                  value={observableForm.type}
                  onChange={(value: string) => setObservableForm((current) => ({ ...current, type: value }))}
                  options={[
                    { value: 'ip', label: 'IP' },
                    { value: 'domain', label: 'Domain' },
                    { value: 'url', label: 'URL' },
                    { value: 'hash', label: 'Hash' },
                    { value: 'email', label: 'Email' },
                  ]}
                />
                <Input
                  value={observableForm.value}
                  onChange={(e) => setObservableForm((current) => ({ ...current, value: e.target.value }))}
                  placeholder="Observable value"
                />
                <Input
                  value={observableForm.source}
                  onChange={(e) => setObservableForm((current) => ({ ...current, source: e.target.value }))}
                  placeholder="Source"
                />
                <Button
                  size="sm"
                  onClick={() => observableMutation.mutate()}
                  disabled={!observableForm.value.trim() || observableMutation.isPending}
                >
                  <Search size={13} /> Add
                </Button>
              </div>

              {(!observables || observables.length === 0) ? (
                <div className="text-xs text-muted">No incident observables yet.</div>
              ) : (
                <div className="space-y-2">
                  {observables.map((observable: Observable) => (
                    <div
                      key={observable.id}
                      className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2"
                    >
                      <div className="min-w-0">
                        <div className="text-sm text-heading font-medium break-all">
                          {observable.type}:{observable.value}
                        </div>
                        <div className="text-[11px] text-muted mt-0.5">
                          {observable.source || 'manual'} · {observable.enrichment_status}
                        </div>
                      </div>
                      <span className="text-[10px] text-muted whitespace-nowrap">
                        {timeAgo(observable.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </StaggerChild>

        <StaggerChild>
          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 mb-4">
                <Input
                  type="text"
                  placeholder="Add a comment..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && commentText.trim()) commentMutation.mutate(commentText.trim())
                  }}
                  className="flex-1 text-sm"
                />
                <Button
                  size="sm"
                  disabled={!commentText.trim() || commentMutation.isPending}
                  onClick={() => commentMutation.mutate(commentText.trim())}
                >
                  <MessageSquare size={13} /> Comment
                </Button>
              </div>

              {(!activities || activities.total === 0) ? (
                <div className="text-center py-6">
                  <div className="text-xs text-muted">No activity yet. Comments and incident lifecycle events will appear here.</div>
                </div>
              ) : (
                <div className="relative">
                  {activities.activities.length > 1 && (
                    <div className="absolute left-[7px] top-4 bottom-4 w-px border-l-2 border-dashed border-border/40" />
                  )}
                  <div className="space-y-0">
                    {activities.activities.map((activity) => (
                      <IncidentTimelineEntry
                        key={activity.id}
                        activity={activity}
                        incidentId={id!}
                        isOwnComment={activity.action === 'comment' && analyst?.id === activity.analyst_id}
                      />
                    ))}
                  </div>
                </div>
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

      <Dialog open={showAssignDialog} onClose={() => setShowAssignDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowAssignDialog(false)}>
            <DialogTitle>Assign Incident</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {otherAnalysts.length === 0 ? (
              <div className="text-sm text-muted py-4 text-center">No other active analysts available</div>
            ) : (
              <div className="space-y-1">
                {otherAnalysts.map((person: Analyst) => (
                  <button
                    key={person.id}
                    onClick={() => updateMutation.mutate({ assigned_to: person.id })}
                    disabled={updateMutation.isPending}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-left',
                      'bg-transparent border-none hover:bg-surface-hover cursor-pointer transition-colors',
                    )}
                  >
                    <span className="flex items-center justify-center w-7 h-7 rounded-full bg-accent/15 text-accent shrink-0">
                      <UserCheck size={13} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-heading font-medium">{person.display_name}</div>
                      <div className="text-[11px] text-muted">@{person.username} {person.role === 'admin' && '· admin'}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </DialogBody>
        </DialogContent>
      </Dialog>
    </PageTransition>
  )
}
