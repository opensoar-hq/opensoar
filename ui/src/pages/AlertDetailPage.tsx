import { useState } from 'react'
import { useParams, Link } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  ArrowLeft, Clock, Globe, FileJson,
  Play, CheckCircle, XCircle, ChevronRight,
  UserCheck, Search, Loader, Users, Briefcase, Link2,
  MessageSquare, Copy, Tag, Pencil, History,
} from 'lucide-react'
import { api, type Analyst, type Playbook, type AvailableAction, type ActionExecuteResponse, type PlaybookRun, type Activity, type Incident2 } from '@/api'
import { SeverityBadge, StatusBadge, DeterminationBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { JsonViewer } from '@/components/ui/JsonViewer'
import { Drawer } from '@/components/ui/Drawer'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dropdown, DropdownItem, DropdownSeparator } from '@/components/ui/Dropdown'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/Dialog'
import { Tooltip } from '@/components/ui/Tooltip'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ExecutionPlanCompact } from '@/components/ui/ExecutionPlan'
import { useToast } from '@/components/ui/Toast'
import { PageTransition, StaggerParent, StaggerChild } from '@/components/ui/PageTransition'
import { timeAgo, formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'

// --- Constants ---

const SEVERITY_OPTIONS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const DETERMINATION_OPTIONS = [
  { value: 'unknown', label: 'Unknown' },
  { value: 'malicious', label: 'Malicious' },
  { value: 'suspicious', label: 'Suspicious' },
  { value: 'benign', label: 'Benign' },
]

const ACTION_LABELS: Record<string, string> = {
  status_change: 'Status Changed',
  severity_change: 'Severity Changed',
  determination_set: 'Determination Set',
  assigned: 'Assigned',
  claimed: 'Claimed',
  manual_action: 'Action Executed',
  comment: 'Comment',
  playbook_triggered: 'Playbook Triggered',
  incident_linked: 'Incident Linked',
  ioc_enriched: 'IOC Enriched',
  resolved: 'Resolved',
}

const ACTION_COLORS: Record<string, string> = {
  status_change: 'var(--color-info)',
  severity_change: 'var(--color-warning)',
  determination_set: 'var(--color-success)',
  assigned: 'var(--color-info)',
  claimed: 'var(--color-success)',
  manual_action: 'var(--color-info)',
  comment: 'var(--color-text)',
  playbook_triggered: 'var(--color-info)',
  incident_linked: 'var(--color-info)',
  resolved: 'var(--color-muted)',
}

// --- IOC Components ---

function IOCValue({
  type, value, alertId, actions,
}: {
  type: string; value: string; alertId: string; actions: AvailableAction[]
}) {
  const [result, setResult] = useState<ActionExecuteResponse | null>(null)
  const queryClient = useQueryClient()

  const executeMutation = useMutation({
    mutationFn: (actionName: string) =>
      api.actions.execute({ action_name: actionName, ioc_type: type, ioc_value: value, alert_id: alertId }),
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: ['alert-activities', alertId] })
    },
  })

  const relevantActions = actions.filter((a) => a.ioc_types.includes(type))

  return (
    <div className="group/ioc flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-bg border border-border hover:border-accent/30 transition-colors">
      <span className="text-xs font-mono text-heading">{value}</span>
      {relevantActions.length > 0 && (
        <Dropdown
          trigger={
            <button
              onClick={() => setResult(null)}
              className="p-0.5 rounded hover:bg-accent/10 bg-transparent border-none cursor-pointer text-muted hover:text-accent opacity-0 group-hover/ioc:opacity-100 transition-opacity"
              title="Enrich"
            >
              <Search size={11} />
            </button>
          }
          className="w-64"
        >
          <div className="px-3 py-2 text-[11px] text-muted uppercase tracking-wide" onClick={(e) => e.stopPropagation()}>
            Enrich {value}
          </div>
          <DropdownSeparator />
          {relevantActions.map((action) => (
            <DropdownItem key={action.name} onClick={() => executeMutation.mutate(action.name)} disabled={executeMutation.isPending}>
              {executeMutation.isPending && executeMutation.variables === action.name ? (
                <Loader size={12} className="animate-spin text-info" />
              ) : (
                <Play size={12} className="text-muted" />
              )}
              <div>
                <div className="font-medium">{action.description}</div>
                <div className="text-[10px] text-muted">{action.integration}</div>
              </div>
            </DropdownItem>
          ))}
          {result && (
            <>
              <DropdownSeparator />
              <div className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-1.5 mb-1.5">
                  {result.status === 'success' ? <CheckCircle size={12} className="text-success" /> : <XCircle size={12} className="text-danger" />}
                  <span className="text-[11px] font-medium text-heading">{result.action_name}</span>
                </div>
                {result.error && <div className="text-[11px] text-danger">{result.error}</div>}
                {result.result && <div className="max-h-40 overflow-auto"><JsonViewer data={result.result} /></div>}
              </div>
            </>
          )}
        </Dropdown>
      )}
    </div>
  )
}

function IOCPanel({ iocs, alertId, actions }: { iocs: Record<string, string[]>; alertId: string; actions: AvailableAction[] }) {
  if (!iocs || Object.keys(iocs).length === 0) return null
  const typeLabels: Record<string, string> = { ips: 'IPs', domains: 'Domains', hashes: 'Hashes', urls: 'URLs' }
  return (
    <div className="space-y-3">
      {Object.entries(iocs).map(([type, values]) => (
        <div key={type}>
          <div className="text-[11px] text-muted uppercase tracking-wide mb-1.5 flex items-center gap-1.5">
            <Globe size={10} /> {typeLabels[type] || type}
            <span className="text-accent font-medium">{values.length}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {values.map((v) => <IOCValue key={v} type={type} value={v} alertId={alertId} actions={actions} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Quick Run Button ---

function QuickRunButton({ playbook, alertId }: { playbook: Playbook; alertId: string }) {
  const queryClient = useQueryClient()
  const toast = useToast()

  const mutation = useMutation({
    mutationFn: () => api.playbooks.run(playbook.id, { alert_id: alertId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-runs', alertId] })
      queryClient.invalidateQueries({ queryKey: ['alert-activities', alertId] })
      toast.success(`${playbook.name} triggered`)
    },
    onError: () => toast.error(`Failed to run ${playbook.name}`),
  })

  return (
    <button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-left',
        'bg-transparent border border-border hover:border-accent/40 hover:bg-surface-hover',
        'cursor-pointer transition-all group',
        mutation.isPending && 'opacity-60 cursor-wait',
      )}
    >
      {mutation.isPending
        ? <Loader size={13} className="text-info animate-spin shrink-0" />
        : <Play size={13} className="text-muted group-hover:text-accent shrink-0 transition-colors" />}
      <div className="flex-1 min-w-0">
        <div className="text-xs text-heading font-medium truncate">{playbook.name}</div>
        {playbook.description && <div className="text-[10px] text-muted truncate">{playbook.description}</div>}
      </div>
      <ChevronRight size={12} className="text-muted opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
    </button>
  )
}

// --- Inline Editable Field ---

function InlineEdit({
  value, onSave, placeholder, label,
}: {
  value: string; onSave: (v: string) => void; placeholder: string; label: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  if (editing) {
    return (
      <div>
        <div className="text-[11px] text-muted uppercase tracking-wide mb-1">{label}</div>
        <div className="flex gap-1.5">
          <Input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { onSave(draft); setEditing(false) }
              if (e.key === 'Escape') { setDraft(value); setEditing(false) }
            }}
            placeholder={placeholder}
            className="!py-1 !text-xs flex-1"
            autoFocus
          />
          <Button size="sm" variant="primary" onClick={() => { onSave(draft); setEditing(false) }}>
            <CheckCircle size={12} />
          </Button>
          <Button size="sm" variant="ghost" onClick={() => { setDraft(value); setEditing(false) }}>
            <XCircle size={12} />
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="text-[11px] text-muted uppercase tracking-wide mb-1">{label}</div>
      <button
        onClick={() => { setDraft(value); setEditing(true) }}
        className="text-sm text-heading bg-transparent border-none cursor-pointer p-0 hover:text-accent transition-colors text-left"
      >
        {value || <span className="text-muted italic">{placeholder}</span>}
      </button>
    </div>
  )
}

// --- Timeline Entry ---

function TimelineEntry({
  activity, index, alertId, isOwnComment,
}: {
  activity: Activity; index: number; alertId: string; isOwnComment: boolean
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [showHistory, setShowHistory] = useState(false)

  const editMutation = useMutation({
    mutationFn: (text: string) => api.alerts.editComment(alertId, activity.id, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-activities', alertId] })
      setEditing(false)
      toast.success('Comment updated')
    },
    onError: () => toast.error('Failed to edit comment'),
  })

  const isComment = activity.action === 'comment'
  const isEdited = activity.created_at !== activity.updated_at
  const editHistory = (activity.metadata_json?.edit_history as Array<{ text: string; edited_at: string }>) || []

  return (
    <motion.div
      className="relative pl-6 pb-4 last:pb-0"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03, type: 'spring', stiffness: 500, damping: 25 }}
    >
      <motion.div
        className={cn(
          'absolute left-0 top-1.5 w-[15px] h-[15px] rounded-full border-2 flex items-center justify-center',
          isComment ? 'border-accent/40 bg-accent/10' : 'border-border bg-surface',
        )}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: index * 0.03 + 0.1, type: 'spring', stiffness: 500, damping: 20 }}
      >
        {isComment ? (
          <MessageSquare size={7} className="text-accent" />
        ) : (
          <div
            className="w-[7px] h-[7px] rounded-full"
            style={{ backgroundColor: ACTION_COLORS[activity.action] || 'var(--color-muted)' }}
          />
        )}
      </motion.div>
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

        {/* Comment body — editable */}
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
        {activity.metadata_json && activity.action === 'manual_action' && !!activity.metadata_json.result && (
          <div className="mt-1.5 max-h-32 overflow-auto">
            <JsonViewer data={activity.metadata_json.result as Record<string, unknown>} />
          </div>
        )}
      </div>
    </motion.div>
  )
}

// --- Main Page ---

export function AlertDetailPage() {
  const { id } = useParams()
  const queryClient = useQueryClient()
  const { analyst } = useAuth()
  const toast = useToast()
  const [rawDrawerOpen, setRawDrawerOpen] = useState(false)
  const [resolveReason, setResolveReason] = useState('')
  const [resolveDetermination, setResolveDetermination] = useState('')
  const [resolvePartner, setResolvePartner] = useState('')
  const [showResolveDialog, setShowResolveDialog] = useState(false)
  const [showAssignDialog, setShowAssignDialog] = useState(false)
  const [showCreateIncidentDialog, setShowCreateIncidentDialog] = useState(false)
  const [showLinkIncidentDialog, setShowLinkIncidentDialog] = useState(false)
  const [incidentSearch, setIncidentSearch] = useState('')
  const [incidentForm, setIncidentForm] = useState({
    title: '',
    severity: 'high',
    description: '',
  })
  const [commentText, setCommentText] = useState('')
  const [triggerPlaybookId, setTriggerPlaybookId] = useState('')

  const { data: alert, isLoading } = useQuery({
    queryKey: ['alert', id],
    queryFn: () => api.alerts.get(id!),
    enabled: !!id,
  })

  const { data: alertRuns } = useQuery({
    queryKey: ['alert-runs', id],
    queryFn: () => api.alerts.getRuns(id!),
    enabled: !!id,
  })

  const { data: linkedIncidents } = useQuery({
    queryKey: ['alert-incidents', id],
    queryFn: () => api.alerts.getIncidents(id!),
    enabled: !!id,
  })

  const { data: activities } = useQuery({
    queryKey: ['alert-activities', id],
    queryFn: () => api.alerts.getActivities(id!),
    enabled: !!id,
  })

  const { data: playbooks } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => api.playbooks.list(),
  })

  const { data: availableActions } = useQuery({
    queryKey: ['available-actions'],
    queryFn: () => api.actions.available(),
  })

  const { data: analysts } = useQuery({
    queryKey: ['analysts'],
    queryFn: api.analysts.list,
  })

  const { data: incidentOptions } = useQuery({
    queryKey: ['incidents', 'link-options'],
    queryFn: () => api.incidents.list({ limit: 100 }),
    enabled: showLinkIncidentDialog,
  })

  const invalidateAlert = () => {
    queryClient.invalidateQueries({ queryKey: ['alert', id] })
    queryClient.invalidateQueries({ queryKey: ['alerts'] })
    queryClient.invalidateQueries({ queryKey: ['alert-activities', id] })
    queryClient.invalidateQueries({ queryKey: ['alert-incidents', id] })
    queryClient.invalidateQueries({ queryKey: ['incidents'] })
  }

  const updateMutation = useMutation({
    mutationFn: (data: { status?: string; severity?: string; resolve_reason?: string; determination?: string; partner?: string; assigned_to?: string }) =>
      api.alerts.update(id!, data),
    onSuccess: (_data, variables) => {
      invalidateAlert()
      if (variables.status === 'resolved') {
        setShowResolveDialog(false)
        setResolveReason('')
        setResolveDetermination('')
        setResolvePartner('')
        toast.success('Alert resolved')
      } else if (variables.determination) {
        toast.success('Determination updated')
      } else if (variables.severity) {
        toast.success('Severity updated')
      } else if (variables.partner !== undefined) {
        toast.success('Partner updated')
      } else if (variables.assigned_to) {
        setShowAssignDialog(false)
        toast.success('Alert reassigned')
      } else {
        toast.success('Alert updated')
      }
    },
    onError: () => toast.error('Failed to update alert'),
  })

  const claimMutation = useMutation({
    mutationFn: () => api.alerts.claim(id!),
    onSuccess: () => { invalidateAlert(); toast.success('Alert claimed') },
    onError: () => toast.error('Failed to claim alert'),
  })

  const commentMutation = useMutation({
    mutationFn: (text: string) => api.alerts.addComment(id!, text),
    onSuccess: () => {
      setCommentText('')
      queryClient.invalidateQueries({ queryKey: ['alert-activities', id] })
      toast.success('Comment added')
    },
    onError: () => toast.error('Failed to add comment'),
  })

  const triggerMutation = useMutation({
    mutationFn: (playbookId: string) => api.playbooks.run(playbookId, { alert_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-runs', id] })
      queryClient.invalidateQueries({ queryKey: ['alert-activities', id] })
      toast.success('Playbook triggered')
      setTriggerPlaybookId('')
    },
    onError: () => toast.error('Failed to trigger playbook'),
  })

  const createIncidentMutation = useMutation({
    mutationFn: () => api.alerts.attachIncident(id!, {
      title: incidentForm.title.trim(),
      severity: incidentForm.severity,
      description: incidentForm.description.trim() || undefined,
    }),
    onSuccess: (incident) => {
      invalidateAlert()
      setShowCreateIncidentDialog(false)
      setIncidentForm({ title: '', severity: 'high', description: '' })
      toast.success(`Created incident ${incident.title}`)
    },
    onError: () => toast.error('Failed to create incident'),
  })

  const linkIncidentMutation = useMutation({
    mutationFn: (incidentId: string) => api.alerts.attachIncident(id!, { incident_id: incidentId }),
    onSuccess: (incident) => {
      invalidateAlert()
      setShowLinkIncidentDialog(false)
      setIncidentSearch('')
      toast.success(`Linked to ${incident.title}`)
    },
    onError: () => toast.error('Failed to link incident'),
  })

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-4xl">
        <CardSkeleton lines={3} />
        <CardSkeleton lines={4} />
        <CardSkeleton lines={6} />
      </div>
    )
  }

  if (!alert) return <div className="text-center py-20 text-muted">Alert not found</div>

  const playbookMap = new Map<string, Playbook>()
  playbooks?.forEach((p) => playbookMap.set(p.id, p))

  const isResolved = alert.status === 'resolved'
  const isUnassigned = !alert.assigned_to
  const isAssignedToMe = analyst && alert.assigned_to === analyst.id
  const hasIOCs = alert.iocs && Object.keys(alert.iocs).length > 0
  const enabledPlaybooks = playbooks?.filter((p) => p.enabled) || []
  const otherAnalysts = (analysts || []).filter((a: Analyst) => a.is_active && a.id !== alert.assigned_to)
  const linkedIncidentIds = new Set((linkedIncidents || []).map((incident) => incident.id))
  const availableIncidents = (incidentOptions?.incidents || []).filter((incident) => {
    if (linkedIncidentIds.has(incident.id)) {
      return false
    }
    if (!incidentSearch.trim()) {
      return true
    }
    const term = incidentSearch.trim().toLowerCase()
    return (
      incident.title.toLowerCase().includes(term)
      || incident.id.toLowerCase().includes(term)
      || (incident.assigned_username || '').toLowerCase().includes(term)
    )
  })

  const openCreateIncidentDialog = () => {
    setIncidentForm({
      title: alert.title,
      severity: alert.severity,
      description: alert.description || '',
    })
    setShowCreateIncidentDialog(true)
  }

  return (
    <PageTransition>
      <Link to="/alerts" className="inline-flex items-center gap-1 text-xs text-muted hover:text-heading no-underline mb-4">
        <ArrowLeft size={14} /> Alerts
      </Link>

      <div className="grid grid-cols-12 gap-5">
        {/* ===== Left: Main content ===== */}
        <StaggerParent className="col-span-12 lg:col-span-8 space-y-4">

          {/* --- Header --- */}
          <StaggerChild>
            <Card>
              <CardContent>
                <div className="flex items-start gap-4 mb-3">
                  <h1 className="text-base font-semibold text-heading m-0 flex-1 min-w-0 leading-snug">
                    {alert.title}
                  </h1>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {!isResolved && (
                      <>
                        {analyst && isUnassigned && (
                          <Button variant="primary" size="sm" onClick={() => claimMutation.mutate()} disabled={claimMutation.isPending}>
                            <UserCheck size={13} /> Claim
                          </Button>
                        )}
                        {analyst && isAssignedToMe && (
                          <Button variant="ghost" size="sm" onClick={() => setShowAssignDialog(true)}>
                            <Users size={13} /> Reassign
                          </Button>
                        )}
                        {analyst && !isUnassigned && !isAssignedToMe && (
                          <Dropdown
                            trigger={
                              <Button size="sm"><UserCheck size={13} /> Assign</Button>
                            }
                            className="w-48"
                          >
                            <DropdownItem onClick={() => claimMutation.mutate()}>
                              <UserCheck size={12} /> Assign to me
                            </DropdownItem>
                            <DropdownItem onClick={() => setShowAssignDialog(true)}>
                              <Users size={12} /> Assign to someone else
                            </DropdownItem>
                          </Dropdown>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => setShowResolveDialog(true)}>
                          Resolve
                        </Button>
                      </>
                    )}
                    {isResolved && (
                      <Button size="sm" onClick={() => updateMutation.mutate({ status: 'in_progress' })} disabled={updateMutation.isPending}>
                        Reopen
                      </Button>
                    )}
                  </div>
                </div>

                {alert.description && <p className="text-sm text-text m-0 mb-3">{alert.description}</p>}

                {/* Compact badge row — identity at a glance */}
                <div className="flex items-center gap-2 flex-wrap">
                  <SeverityBadge severity={alert.severity} />
                  <StatusBadge status={alert.status} />
                  {alert.determination && alert.determination !== 'unknown' && (
                    <DeterminationBadge determination={alert.determination} />
                  )}
                  {alert.partner && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-surface-hover text-heading">
                      <Tag size={9} /> {alert.partner}
                    </span>
                  )}
                  {alert.assigned_username && (
                    <span className="flex items-center gap-1 text-[11px] text-accent">
                      <UserCheck size={11} /> {alert.assigned_username}
                    </span>
                  )}
                  {alert.duplicate_count > 1 && (
                    <Tooltip content={`${alert.duplicate_count} duplicate alerts`}>
                      <span className="text-[10px] text-warning bg-warning/15 px-1.5 py-0.5 rounded font-medium">
                        <Copy size={9} className="inline mr-0.5 align-[-1px]" />{alert.duplicate_count}x
                      </span>
                    </Tooltip>
                  )}
                  <span className="text-border">|</span>
                  <Tooltip content={formatDate(alert.created_at)}>
                    <span className="text-[11px] text-muted flex items-center gap-1"><Clock size={10} /> {timeAgo(alert.created_at)}</span>
                  </Tooltip>
                  <span className="text-[11px] text-muted flex items-center gap-1"><Globe size={10} /> {alert.source}</span>
                </div>
              </CardContent>
            </Card>
          </StaggerChild>

          {/* --- Triage: analyst-settable fields --- */}
          <StaggerChild>
            <Card>
              <CardHeader>
                <CardTitle>Triage</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-8 gap-y-4">
                  <div>
                    <div className="text-[11px] text-muted uppercase tracking-wide mb-1">Severity</div>
                    {!isResolved ? (
                      <Select
                        value={alert.severity}
                        onChange={(v) => updateMutation.mutate({ severity: v })}
                        options={SEVERITY_OPTIONS}
                      />
                    ) : (
                      <SeverityBadge severity={alert.severity} />
                    )}
                  </div>
                  <div>
                    <div className="text-[11px] text-muted uppercase tracking-wide mb-1">Determination</div>
                    {!isResolved ? (
                      <Select
                        value={alert.determination || 'unknown'}
                        onChange={(v) => updateMutation.mutate({ determination: v })}
                        options={DETERMINATION_OPTIONS}
                      />
                    ) : (
                      <DeterminationBadge determination={alert.determination || 'unknown'} />
                    )}
                  </div>
                  {!isResolved ? (
                    <InlineEdit
                      label="Partner"
                      value={alert.partner || ''}
                      onSave={(v) => updateMutation.mutate({ partner: v })}
                      placeholder="Set partner..."
                    />
                  ) : (
                    <ReadonlyField label="Partner" value={alert.partner} />
                  )}
                </div>
                {isResolved && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-8 gap-y-4 mt-4 pt-4 border-t border-border">
                    {alert.resolved_at && <ReadonlyField label="Resolved" value={formatDate(alert.resolved_at)} />}
                    {alert.resolve_reason && <ReadonlyField label="Reason" value={alert.resolve_reason} />}
                  </div>
                )}
              </CardContent>
            </Card>
          </StaggerChild>

          {/* --- Alert Context: read-only metadata --- */}
          <StaggerChild>
            <Card>
              <CardHeader>
                <CardTitle>Alert Context</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-8 gap-y-3">
                  <ReadonlyField label="Source" value={alert.source} />
                  <ReadonlyField label="Rule" value={alert.rule_name} />
                  <ReadonlyField label="Source IP" value={alert.source_ip} mono />
                  <ReadonlyField label="Dest IP" value={alert.dest_ip} mono />
                  <ReadonlyField label="Hostname" value={alert.hostname} mono />
                  {alert.source_id && <ReadonlyField label="Source ID" value={alert.source_id} mono />}
                </div>
                {alert.tags && alert.tags.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-border">
                    <div className="flex gap-1 flex-wrap">
                      {alert.tags.map((t) => (
                        <span key={t} className="px-2 py-0.5 text-[11px] bg-bg border border-border rounded text-heading">{t}</span>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </StaggerChild>

          {/* --- IOCs --- */}
          {hasIOCs && (
            <StaggerChild>
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <CardTitle>Indicators of Compromise</CardTitle>
                    <span className="text-[11px] text-accent bg-accent/10 px-2 py-0.5 rounded-full font-medium">
                      {Object.values(alert.iocs!).reduce((a, b) => a + b.length, 0)}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <IOCPanel iocs={alert.iocs!} alertId={id!} actions={availableActions || []} />
                </CardContent>
              </Card>
            </StaggerChild>
          )}

          {/* --- Playbook Runs --- */}
          {alertRuns && alertRuns.runs.length > 0 && (
            <StaggerChild>
              <Card>
                <CardHeader>
                  <CardTitle>Playbook Runs</CardTitle>
                </CardHeader>
                <div className="divide-y divide-border">
                  {alertRuns.runs.map((run: PlaybookRun) => (
                    <ExecutionPlanCompact
                      key={run.id}
                      run={{
                        id: run.id,
                        playbook_name: playbookMap.get(run.playbook_id)?.name || run.playbook_id.slice(0, 8),
                        status: run.status,
                        started_at: run.started_at,
                        finished_at: run.finished_at,
                        error: run.error,
                        result: run.result,
                        steps: run.action_results,
                      }}
                      playbookName={playbookMap.get(run.playbook_id)?.name || run.playbook_id.slice(0, 8)}
                    />
                  ))}
                </div>
              </Card>
            </StaggerChild>
          )}

          {/* --- Unified Timeline --- */}
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
                    <div className="text-xs text-muted">No activity yet. Comments and system events will appear here.</div>
                  </div>
                ) : (
                  <div className="relative">
                    {activities.activities.length > 1 && (
                      <div className="absolute left-[7px] top-4 bottom-4 w-px border-l-2 border-dashed border-border/40" />
                    )}
                    <div className="space-y-0">
                      {activities.activities.map((activity, i) => (
                        <TimelineEntry
                          key={activity.id}
                          activity={activity}
                          index={i}
                          alertId={id!}
                          isOwnComment={activity.action === 'comment' && analyst?.id === activity.analyst_id}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </StaggerChild>

          {/* --- Evidence --- */}
          {(alert.normalized && Object.keys(alert.normalized).length > 0) && (
            <StaggerChild>
              <Card>
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>Normalized Data</CardTitle>
                  {alert.raw_payload && Object.keys(alert.raw_payload).length > 0 && (
                    <Button variant="ghost" size="sm" onClick={() => setRawDrawerOpen(true)}>
                      <FileJson size={14} /> Raw Payload
                    </Button>
                  )}
                </CardHeader>
                <CardContent>
                  <JsonViewer data={alert.normalized} />
                </CardContent>
              </Card>
            </StaggerChild>
          )}

          {(!alert.normalized || Object.keys(alert.normalized).length === 0) && alert.raw_payload && Object.keys(alert.raw_payload).length > 0 && (
            <StaggerChild>
              <Card>
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>Raw Payload</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => setRawDrawerOpen(true)}>
                    <FileJson size={14} /> Expand
                  </Button>
                </CardHeader>
              </Card>
            </StaggerChild>
          )}
        </StaggerParent>

        {/* ===== Right: Sidebar ===== */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>Incidents</CardTitle>
              <div className="flex items-center gap-1.5">
                <Button variant="ghost" size="sm" onClick={openCreateIncidentDialog} disabled={createIncidentMutation.isPending}>
                  <Briefcase size={13} /> Create
                </Button>
                <Button size="sm" onClick={() => setShowLinkIncidentDialog(true)} disabled={linkIncidentMutation.isPending}>
                  <Link2 size={13} /> Link
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {(!linkedIncidents || linkedIncidents.length === 0) ? (
                <div className="text-xs text-muted">
                  No incidents linked yet. Create one from this alert or link it to an existing incident.
                </div>
              ) : (
                <div className="space-y-2">
                  {linkedIncidents.map((incident: Incident2) => (
                    <Link
                      key={incident.id}
                      to={`/incidents/${incident.id}`}
                      className="block no-underline rounded-md border border-border px-3 py-2 hover:border-accent/40 hover:bg-surface-hover transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-sm text-heading font-medium truncate">{incident.title}</div>
                          <div className="text-[11px] text-muted mt-0.5">
                            {incident.alert_count} alert{incident.alert_count !== 1 ? 's' : ''}
                            {incident.assigned_username ? ` · ${incident.assigned_username}` : ''}
                          </div>
                        </div>
                        <StatusBadge status={incident.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Run Playbook */}
          {enabledPlaybooks.length > 0 && !isResolved && (
            <Card>
              <CardHeader>
                <CardTitle>Run Playbook</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {enabledPlaybooks.slice(0, 4).map((p) => (
                    <QuickRunButton key={p.id} playbook={p} alertId={id!} />
                  ))}
                  {enabledPlaybooks.length > 4 && (
                    <div className="pt-1">
                      <div className="flex items-center gap-2">
                        <Select
                          value={triggerPlaybookId}
                          onChange={setTriggerPlaybookId}
                          options={[
                            { value: '', label: 'More playbooks...' },
                            ...enabledPlaybooks.slice(4).map((p) => ({ value: p.id, label: p.name })),
                          ]}
                          className="flex-1"
                        />
                        <Button
                          variant="primary" size="sm"
                          disabled={!triggerPlaybookId || triggerMutation.isPending}
                          onClick={() => triggerMutation.mutate(triggerPlaybookId)}
                        >
                          <Play size={13} />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Alert info */}
          <Card>
            <CardHeader>
              <CardTitle>Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              <SidebarField label="Created" value={formatDate(alert.created_at)} />
              <SidebarField label="Updated" value={formatDate(alert.updated_at)} />
              <SidebarField label="Source" value={alert.source} />
              {alert.rule_name && <SidebarField label="Rule" value={alert.rule_name} />}
              {alert.source_ip && <SidebarField label="Source IP" value={alert.source_ip} mono />}
              {alert.hostname && <SidebarField label="Host" value={alert.hostname} mono />}
              <SidebarField label="ID" value={alert.id.slice(0, 8)} mono />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* --- Resolve Dialog --- */}
      <Dialog open={showResolveDialog} onClose={() => setShowResolveDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowResolveDialog(false)}>
            <DialogTitle>Resolve Alert</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div>
              <div className="text-[11px] text-muted uppercase tracking-wide mb-1">Determination <span className="text-danger">*</span></div>
              <Select
                value={resolveDetermination || (alert.determination !== 'unknown' ? alert.determination : '')}
                onChange={setResolveDetermination}
                options={[
                  { value: '', label: 'Select determination...' },
                  ...DETERMINATION_OPTIONS.filter((o) => o.value !== 'unknown'),
                ]}
                className="w-full"
              />
            </div>
            <div>
              <div className="text-[11px] text-muted uppercase tracking-wide mb-1">Partner <span className="text-muted">(optional)</span></div>
              <Input
                type="text"
                placeholder="Partner / tenant name"
                value={resolvePartner || alert.partner || ''}
                onChange={(e) => setResolvePartner(e.target.value)}
              />
            </div>
            <div>
              <div className="text-[11px] text-muted uppercase tracking-wide mb-1">Reason <span className="text-muted">(optional)</span></div>
              <Input
                type="text"
                placeholder="Resolve reason"
                value={resolveReason}
                onChange={(e) => setResolveReason(e.target.value)}
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setShowResolveDialog(false)}>Cancel</Button>
            <Button
              variant="primary" size="sm"
              onClick={() => {
                const det = resolveDetermination || (alert.determination !== 'unknown' ? alert.determination : '')
                if (!det) {
                  toast.error('Set a determination before resolving')
                  return
                }
                const data: Record<string, string | undefined> = {
                  status: 'resolved',
                  determination: det,
                }
                const partner = (resolvePartner || alert.partner || '').trim()
                if (partner) data.partner = partner
                if (resolveReason) data.resolve_reason = resolveReason
                updateMutation.mutate(data)
              }}
              disabled={updateMutation.isPending}
            >
              Resolve Alert
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* --- Reassign Dialog --- */}
      <Dialog open={showAssignDialog} onClose={() => setShowAssignDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowAssignDialog(false)}>
            <DialogTitle>Reassign Alert</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {otherAnalysts.length === 0 ? (
              <div className="text-sm text-muted py-4 text-center">No other active analysts available</div>
            ) : (
              <div className="space-y-1">
                {otherAnalysts.map((a: Analyst) => (
                  <button
                    key={a.id}
                    onClick={() => updateMutation.mutate({ assigned_to: a.id })}
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
                      <div className="text-sm text-heading font-medium">{a.display_name}</div>
                      <div className="text-[11px] text-muted">@{a.username} {a.role === 'admin' && '· admin'}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </DialogBody>
        </DialogContent>
      </Dialog>

      <Dialog open={showCreateIncidentDialog} onClose={() => setShowCreateIncidentDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowCreateIncidentDialog(false)}>
            <DialogTitle>Create Incident from Alert</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <div>
              <Label>Title</Label>
              <Input
                value={incidentForm.title}
                onChange={(e) => setIncidentForm((current) => ({ ...current, title: e.target.value }))}
                placeholder="Incident title"
              />
            </div>
            <div>
              <Label>Severity</Label>
              <Select
                value={incidentForm.severity}
                onChange={(value) => setIncidentForm((current) => ({ ...current, severity: value }))}
                options={SEVERITY_OPTIONS}
                className="w-full"
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                value={incidentForm.description}
                onChange={(e) => setIncidentForm((current) => ({ ...current, description: e.target.value }))}
                placeholder="Optional incident description"
                rows={4}
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setShowCreateIncidentDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => createIncidentMutation.mutate()}
              disabled={!incidentForm.title.trim() || createIncidentMutation.isPending}
            >
              {createIncidentMutation.isPending ? 'Creating...' : 'Create Incident'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showLinkIncidentDialog} onClose={() => setShowLinkIncidentDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowLinkIncidentDialog(false)}>
            <DialogTitle>Link to Existing Incident</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <div>
              <Label>Search</Label>
              <Input
                value={incidentSearch}
                onChange={(e) => setIncidentSearch(e.target.value)}
                placeholder="Filter incidents by title, ID, or assignee..."
              />
            </div>
            <div className="max-h-72 overflow-auto space-y-1">
              {availableIncidents.length === 0 ? (
                <div className="text-sm text-muted py-4 text-center">
                  No matching incidents available to link.
                </div>
              ) : (
                availableIncidents.map((incident: Incident2) => (
                  <button
                    key={incident.id}
                    onClick={() => linkIncidentMutation.mutate(incident.id)}
                    disabled={linkIncidentMutation.isPending}
                    className={cn(
                      'w-full flex items-start gap-3 px-3 py-2.5 rounded-md text-left',
                      'bg-transparent border-none hover:bg-surface-hover cursor-pointer transition-colors',
                    )}
                  >
                    <span className="flex items-center justify-center w-7 h-7 rounded-full bg-accent/15 text-accent shrink-0">
                      <Briefcase size={13} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-heading font-medium truncate">{incident.title}</div>
                      <div className="text-[11px] text-muted mt-0.5">
                        {incident.status} · {incident.severity}
                        {incident.assigned_username ? ` · ${incident.assigned_username}` : ''}
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </DialogBody>
        </DialogContent>
      </Dialog>

      <Drawer open={rawDrawerOpen} onClose={() => setRawDrawerOpen(false)} title="Raw Payload">
        <JsonViewer data={alert.raw_payload || {}} />
      </Drawer>
    </PageTransition>
  )
}

// --- Helpers ---

function ReadonlyField({ label, value, mono = false }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div>
      <div className="text-[11px] text-muted uppercase tracking-wide mb-0.5">{label}</div>
      <div className={cn('text-sm text-heading', mono && 'font-mono')}>{value || '—'}</div>
    </div>
  )
}

function SidebarField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-muted uppercase tracking-wide">{label}</span>
      <span className={cn('text-xs text-heading', mono && 'font-mono')}>{value}</span>
    </div>
  )
}
