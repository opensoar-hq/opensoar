import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, CheckCircle, XCircle, Clock, Loader, ChevronDown, ExternalLink } from 'lucide-react'
import { api, type PlaybookRun } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusBadge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Select'
import { EmptyState } from '@/components/ui/EmptyState'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Pagination } from '@/components/ui/Pagination'
import { Button } from '@/components/ui/Button'
import { PageTransition } from '@/components/ui/PageTransition'
import { timeAgo, formatDuration, cn } from '@/lib/utils'

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle size={14} className="text-success" />,
  success: <CheckCircle size={14} className="text-success" />,
  failed: <XCircle size={14} className="text-danger" />,
  running: <Loader size={14} className="text-info" />,
  pending: <Clock size={14} className="text-muted" />,
}

const STEP_STATUS_COLORS: Record<string, string> = {
  success: 'text-success',
  completed: 'text-success',
  failed: 'text-danger',
  running: 'text-accent',
  pending: 'text-muted',
}

function ExpandedRunDetails({ run }: { run: PlaybookRun }) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden"
    >
      <div className="px-4 py-3 bg-bg/50 border-t border-border">
        {/* Error */}
        {run.error && (
          <div className="mb-3 px-3 py-2 rounded-md bg-danger/5 border border-danger/20">
            <pre className="text-[11px] font-mono text-danger whitespace-pre-wrap m-0">{run.error}</pre>
          </div>
        )}

        {/* Action steps */}
        {run.action_results.length > 0 ? (
          <div className="space-y-1">
            <div className="text-[10px] text-muted uppercase tracking-wider mb-2 font-semibold">Action Steps</div>
            {run.action_results.map((step, i) => (
              <div key={step.id} className="flex items-center gap-3 px-3 py-1.5 rounded-md hover:bg-surface-hover transition-colors">
                <span className="text-[11px] text-muted w-4 text-right font-mono">{i + 1}</span>
                <span className={cn('shrink-0', STEP_STATUS_COLORS[step.status] || 'text-muted')}>
                  {step.status === 'success' || step.status === 'completed'
                    ? <CheckCircle size={12} />
                    : step.status === 'failed'
                      ? <XCircle size={12} />
                      : step.status === 'running'
                        ? <Loader size={12} className="animate-spin" />
                        : <Clock size={12} />}
                </span>
                <span className="text-xs text-heading font-medium flex-1 truncate">{step.action_name}</span>
                {step.duration_ms != null && (
                  <span className="text-[11px] font-mono text-muted">{step.duration_ms}ms</span>
                )}
                <StatusBadge status={step.status} />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-muted text-center py-3">No action steps recorded</div>
        )}

        {/* Link to full detail */}
        <div className="mt-3 pt-2 border-t border-border flex justify-end">
          <Link
            to={`/runs/${run.id}`}
            className="inline-flex items-center gap-1 text-[11px] text-accent no-underline hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            View full details <ExternalLink size={10} />
          </Link>
        </div>
      </div>
    </motion.div>
  )
}

export function RunsListPage() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState<{ status?: string; playbook_id?: string }>({})
  const [page, setPage] = useState(0)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const limit = 50

  const { data, isLoading } = useQuery({
    queryKey: ['runs', filters, page],
    queryFn: () => api.runs.list({ ...filters, limit, offset: page * limit }),
  })

  const { data: playbooks } = useQuery({
    queryKey: ['playbooks'],
    queryFn: api.playbooks.list,
  })

  const playbookMap = new Map<string, string>()
  playbooks?.forEach((p) => playbookMap.set(p.id, p.name))

  return (
    <PageTransition>
      <PageHeader icon={<Play size={18} />} title="Playbook Runs" count={data?.total}>
        <div className="flex items-center gap-2">
          <Select
            value={filters.status || ''}
            onChange={(v) => { setFilters((f) => ({ ...f, status: v || undefined })); setPage(0) }}
            options={[
              { value: '', label: 'All statuses' },
              { value: 'success', label: 'Success' },
              { value: 'failed', label: 'Failed' },
              { value: 'running', label: 'Running' },
              { value: 'pending', label: 'Pending' },
            ]}
          />
          {playbooks && playbooks.length > 0 && (
            <Select
              value={filters.playbook_id || ''}
              onChange={(v) => { setFilters((f) => ({ ...f, playbook_id: v || undefined })); setPage(0) }}
              options={[
                { value: '', label: 'All playbooks' },
                ...playbooks.map((p) => ({ value: p.id, label: p.name })),
              ]}
            />
          )}
        </div>
      </PageHeader>

      {isLoading && <TableSkeleton rows={8} cols={7} />}

      {!isLoading && (!data || data.runs.length === 0) && (
        <EmptyState icon={<Play size={32} />} title="No playbook runs" description="Runs will appear here when playbooks are triggered" />
      )}

      {!isLoading && data && data.runs.length > 0 && (
        <>
          <div className="rounded-lg border border-border overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-4 px-4 py-2.5 bg-surface border-b border-border text-[11px] text-muted uppercase tracking-wider font-semibold">
              <span className="w-6" />
              <span className="w-8" />
              <span className="flex-1">Playbook</span>
              <span className="w-28">Status</span>
              <span className="w-24">Duration</span>
              <span className="w-20">Steps</span>
              <span className="w-24">Alert</span>
              <span className="w-24">Time</span>
            </div>

            {/* Rows */}
            <div className="divide-y divide-border">
              {data.runs.map((run) => {
                const isExpanded = expandedId === run.id
                return (
                  <div key={run.id}>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : run.id)}
                      className={cn(
                        'w-full flex items-center gap-4 px-4 py-3 text-left bg-transparent border-none cursor-pointer transition-colors group',
                        isExpanded ? 'bg-surface-hover' : 'hover:bg-surface-hover',
                      )}
                    >
                      <motion.span
                        animate={{ rotate: isExpanded ? 180 : 0 }}
                        transition={{ duration: 0.2 }}
                        className="w-6 flex items-center justify-center shrink-0"
                      >
                        <ChevronDown size={14} className="text-muted" />
                      </motion.span>

                      <span className="w-8 shrink-0 flex items-center justify-center">
                        {STATUS_ICONS[run.status] || <Clock size={14} className="text-muted" />}
                      </span>

                      <span className="flex-1 text-sm text-heading font-medium truncate group-hover:text-accent transition-colors">
                        {playbookMap.get(run.playbook_id) || run.playbook_id.slice(0, 8)}
                      </span>

                      <span className="w-28 shrink-0">
                        <StatusBadge status={run.status} />
                      </span>

                      <span className="w-24 shrink-0 text-xs font-mono text-muted">
                        {formatDuration(run.started_at, run.finished_at)}
                      </span>

                      <span className="w-20 shrink-0 text-xs text-muted">
                        {run.action_results.length} step{run.action_results.length !== 1 ? 's' : ''}
                      </span>

                      <span className="w-24 shrink-0 text-xs" onClick={(e) => e.stopPropagation()}>
                        {run.alert_id ? (
                          <Link
                            to={`/alerts/${run.alert_id}`}
                            className="text-accent no-underline hover:underline"
                          >
                            {run.alert_id.slice(0, 8)}
                          </Link>
                        ) : <span className="text-muted">—</span>}
                      </span>

                      <span className="w-24 shrink-0 text-xs text-muted whitespace-nowrap flex items-center gap-1">
                        <Clock size={11} />
                        {timeAgo(run.created_at)}
                      </span>
                    </button>

                    <AnimatePresence initial={false}>
                      {isExpanded && <ExpandedRunDetails run={run} />}
                    </AnimatePresence>
                  </div>
                )
              })}
            </div>
          </div>

          <Pagination
            page={page}
            total={data.total}
            limit={limit}
            onPageChange={setPage}
          />
        </>
      )}
    </PageTransition>
  )
}
