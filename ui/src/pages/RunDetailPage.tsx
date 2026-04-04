import { useParams, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Clock, AlertTriangle } from 'lucide-react'
import { api, type Playbook } from '@/api'
import { Card, CardContent } from '@/components/ui/Card'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ExecutionPlan } from '@/components/ui/ExecutionPlan'
import { Tooltip } from '@/components/ui/Tooltip'
import { PageTransition, StaggerParent, StaggerChild } from '@/components/ui/PageTransition'
import { timeAgo, formatDate, formatDuration } from '@/lib/utils'

export function RunDetailPage() {
  const { id } = useParams()

  const { data: run, isLoading } = useQuery({
    queryKey: ['run', id],
    queryFn: () => api.runs.get(id!),
    enabled: !!id,
  })

  const { data: playbooks } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => api.playbooks.list(),
  })

  if (isLoading) {
    return (
      <div>
        <Link to="/runs" className="inline-flex items-center gap-1 text-xs text-muted hover:text-heading no-underline mb-4">
          <ArrowLeft size={14} /> Back to runs
        </Link>
        <CardSkeleton lines={3} />
        <div className="mt-6 space-y-3">
          <CardSkeleton lines={2} />
          <CardSkeleton lines={2} />
        </div>
      </div>
    )
  }

  if (!run) {
    return <div className="text-center py-20 text-muted">Run not found</div>
  }

  const playbookMap = new Map<string, Playbook>()
  playbooks?.forEach((p) => playbookMap.set(p.id, p))
  const playbook = playbookMap.get(run.playbook_id)
  const playbookName = playbook?.name || 'Unknown Playbook'

  return (
    <PageTransition>
      <Link to="/runs" className="inline-flex items-center gap-1 text-xs text-muted hover:text-heading no-underline mb-4">
        <ArrowLeft size={14} /> Back to runs
      </Link>

      <StaggerParent>
      {/* Summary bar */}
      <StaggerChild><Card className="mb-6">
        <CardContent>
          <div className="flex flex-wrap items-center gap-4 text-xs text-muted">
            <Tooltip content={formatDate(run.created_at)}>
              <span className="flex items-center gap-1">
                <Clock size={12} /> {timeAgo(run.created_at)}
              </span>
            </Tooltip>
            <span>
              Duration: <span className="font-mono text-heading">{formatDuration(run.started_at, run.finished_at)}</span>
            </span>
            <span>
              Steps: <span className="text-heading">{run.action_results.length}</span>
            </span>
            {run.alert_id && (
              <span>
                Alert: <Link to={`/alerts/${run.alert_id}`} className="text-accent no-underline hover:underline">{run.alert_id.slice(0, 8)}</Link>
              </span>
            )}
          </div>
        </CardContent>
      </Card></StaggerChild>

      {/* Top-level error (if run failed before steps) */}
      {run.error && run.action_results.length === 0 && (
        <StaggerChild><Card className="mb-6 border-danger/30">
          <CardContent className="bg-danger/5">
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="text-danger mt-0.5 shrink-0" />
              <pre className="text-xs font-mono text-danger whitespace-pre-wrap m-0 flex-1">
                {run.error}
              </pre>
            </div>
          </CardContent>
        </Card></StaggerChild>
      )}

      {/* Execution plan */}
      <StaggerChild>
        <ExecutionPlan
          run={{
            id: run.id,
            playbook_name: playbookName,
            status: run.status,
            started_at: run.started_at,
            finished_at: run.finished_at,
            error: run.error,
            result: run.result,
            steps: run.action_results,
          }}
        />
      </StaggerChild>
      </StaggerParent>
    </PageTransition>
  )
}
