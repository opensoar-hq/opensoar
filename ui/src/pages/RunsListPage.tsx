import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { Play, CheckCircle, XCircle, Clock, Loader } from 'lucide-react'
import { api } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusBadge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Select'
import { EmptyState } from '@/components/ui/EmptyState'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Pagination } from '@/components/ui/Pagination'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableHeaderRow,
} from '@/components/ui/Table'
import { PageTransition } from '@/components/ui/PageTransition'
import { timeAgo, formatDuration } from '@/lib/utils'

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle size={14} className="text-success" />,
  success: <CheckCircle size={14} className="text-success" />,
  failed: <XCircle size={14} className="text-danger" />,
  running: <Loader size={14} className="text-accent" />,
  pending: <Clock size={14} className="text-muted" />,
}

export function RunsListPage() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState<{ status?: string; playbook_id?: string }>({})
  const [page, setPage] = useState(0)
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
          <Table>
            <TableHeader>
              <TableHeaderRow>
                <TableHead className="w-8 px-4" />
                <TableHead>Playbook</TableHead>
                <TableHead className="w-28">Status</TableHead>
                <TableHead className="w-24">Duration</TableHead>
                <TableHead className="w-20">Actions</TableHead>
                <TableHead className="w-24">Alert</TableHead>
                <TableHead className="w-24">Time</TableHead>
              </TableHeaderRow>
            </TableHeader>
            <TableBody>
              {data.runs.map((run) => (
                <TableRow key={run.id} onClick={() => navigate(`/runs/${run.id}`)} className="cursor-pointer">
                  <TableCell className="px-4">
                    {STATUS_ICONS[run.status] || <Clock size={14} className="text-muted" />}
                  </TableCell>
                  <TableCell>
                    <span className="text-heading group-hover:text-accent transition-colors">
                      {playbookMap.get(run.playbook_id) || run.playbook_id.slice(0, 8)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={run.status} />
                  </TableCell>
                  <TableCell className="text-xs font-mono text-muted">
                    {formatDuration(run.started_at, run.finished_at)}
                  </TableCell>
                  <TableCell className="text-xs text-muted">
                    {run.action_results.length} step{run.action_results.length !== 1 ? 's' : ''}
                  </TableCell>
                  <TableCell className="text-xs">
                    {run.alert_id ? (
                      <Link
                        to={`/alerts/${run.alert_id}`}
                        className="text-accent no-underline hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {run.alert_id.slice(0, 8)}
                      </Link>
                    ) : <span className="text-muted">—</span>}
                  </TableCell>
                  <TableCell className="text-xs text-muted whitespace-nowrap">
                    <Clock size={11} className="inline mr-1 align-[-1px]" />
                    {timeAgo(run.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

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
