import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import {
  LayoutDashboard, Shield, AlertTriangle, Clock, Play,
  CheckCircle, XCircle, User, ArrowRight, Zap, Inbox,
} from 'lucide-react'
import { api } from '@/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatSkeleton, CardSkeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageTransition, StaggerParent, StaggerChild } from '@/components/ui/PageTransition'
import { useAuth } from '@/contexts/AuthContext'
import { timeAgo } from '@/lib/utils'

function StatCard({ label, value, sub, icon, color, to }: {
  label: string
  value: string | number
  sub?: string
  icon: React.ReactNode
  color: string
  to?: string
}) {
  const content = (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] text-muted uppercase tracking-wide">{label}</span>
        <span className="p-1.5 rounded-md" style={{ color, backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)` }}>
          {icon}
        </span>
      </div>
      <div className="text-2xl font-semibold text-heading">{value}</div>
      {sub && <div className="text-[11px] text-muted mt-1">{sub}</div>}
    </Card>
  )

  if (to) {
    return (
      <Link to={to} className="no-underline block hover:ring-1 hover:ring-accent/30 rounded-lg transition-all">
        {content}
      </Link>
    )
  }
  return content
}

function SeverityBar({ data }: { data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0)
  if (total === 0) return <div className="text-xs text-muted">No alerts</div>
  const order = ['critical', 'high', 'medium', 'low']
  const colors: Record<string, string> = {
    critical: 'var(--color-critical)',
    high: 'var(--color-danger)',
    medium: 'var(--color-warning)',
    low: 'var(--color-info)',
  }
  return (
    <div>
      <div className="flex rounded-md overflow-hidden h-5 mb-2">
        {order.map((sev) => {
          const count = data[sev] || 0
          if (count === 0) return null
          return (
            <div
              key={sev}
              style={{ width: `${(count / total) * 100}%`, backgroundColor: colors[sev] }}
              className="flex items-center justify-center text-[10px] font-medium text-bg transition-all"
              title={`${sev}: ${count}`}
            >
              {count > 0 && count}
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 text-xs">
        {order.map((sev) => (
          <div key={sev} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[sev] }} />
            <span className="text-muted capitalize">{sev}</span>
            <span className="text-heading font-medium">{data[sev] || 0}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatMTTR(seconds: number | null): string {
  if (seconds === null) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-3"><StatSkeleton /></div>
      <div className="col-span-3"><StatSkeleton /></div>
      <div className="col-span-3"><StatSkeleton /></div>
      <div className="col-span-3"><StatSkeleton /></div>
      <div className="col-span-8 space-y-4">
        <CardSkeleton lines={6} />
        <CardSkeleton lines={3} />
      </div>
      <div className="col-span-4 space-y-4">
        <CardSkeleton lines={3} />
        <CardSkeleton lines={4} />
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { analyst } = useAuth()
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard.stats,
  })

  if (isLoading) {
    return (
      <div>
        <PageHeader icon={<LayoutDashboard size={18} />} title="Dashboard" />
        <DashboardSkeleton />
      </div>
    )
  }

  if (!data) return null

  const hasMyAlerts = data.my_alerts.length > 0

  return (
    <PageTransition>
      <PageHeader icon={<LayoutDashboard size={18} />} title="Dashboard" />

      <div className="grid grid-cols-12 gap-4">
        {/* Stats row — 4x 3-col */}
        <StaggerParent className="col-span-12 grid grid-cols-2 md:grid-cols-4 gap-4">
          <StaggerChild>
            <StatCard
              label="Open Alerts"
              value={data.open_alerts}
              sub={`${data.unassigned_count} unassigned`}
              icon={<AlertTriangle size={16} />}
              color="var(--color-warning)"
              to="/alerts?status=new"
            />
          </StaggerChild>
          <StaggerChild>
            <StatCard
              label="Alerts Today"
              value={data.alerts_today}
              sub={`${data.total_alerts} total`}
              icon={<Inbox size={16} />}
              color="var(--color-heading)"
              to="/alerts"
            />
          </StaggerChild>
          <StaggerChild>
            <StatCard
              label="MTTR (7d)"
              value={formatMTTR(data.mttr_seconds)}
              sub="Mean time to resolve"
              icon={<Clock size={16} />}
              color="var(--color-success)"
            />
          </StaggerChild>
          <StaggerChild>
            <StatCard
              label="Active Runs"
              value={data.active_runs}
              sub={`${data.total_runs} total`}
              icon={<Zap size={16} />}
              color="var(--color-heading)"
              to="/runs"
            />
          </StaggerChild>
        </StaggerParent>

        {/* Left column — 8/12 */}
        <StaggerParent className="col-span-12 lg:col-span-8 space-y-4">
          {/* Priority Queue */}
          <StaggerChild>
            <Card>
              <CardHeader className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CardTitle>Priority Queue</CardTitle>
                  <span className="text-[11px] text-muted bg-bg px-2 py-0.5 rounded-full">{data.priority_queue.length}</span>
                </div>
                <Link to="/alerts" className="flex items-center gap-1 text-xs text-accent no-underline hover:underline">
                  All alerts <ArrowRight size={12} />
                </Link>
              </CardHeader>
              {data.priority_queue.length > 0 ? (
                <div className="divide-y divide-border">
                  {data.priority_queue.map((alert) => (
                    <Link
                      key={alert.id}
                      to={`/alerts/${alert.id}`}
                      className="flex items-center gap-3 px-5 py-3 hover:bg-surface-hover no-underline transition-colors group"
                    >
                      <SeverityBadge severity={alert.severity} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-heading truncate group-hover:text-accent transition-colors">
                          {alert.title}
                        </div>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-[11px] text-muted">{alert.source}</span>
                          {alert.source_ip && (
                            <span className="text-[11px] font-mono text-muted">{alert.source_ip}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <StatusBadge status={alert.status} />
                        {alert.assigned_username ? (
                          <span className="flex items-center gap-1 text-[11px] text-accent">
                            <User size={10} /> {alert.assigned_username}
                          </span>
                        ) : (
                          <span className="text-[11px] text-muted/50">unassigned</span>
                        )}
                        <span className="text-[11px] text-muted whitespace-nowrap">{timeAgo(alert.created_at)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <CardContent>
                  <div className="py-6 text-center">
                    <CheckCircle size={24} className="text-success mx-auto mb-2" />
                    <div className="text-sm text-heading font-medium">All clear</div>
                    <div className="text-xs text-muted mt-0.5">No open alerts in the queue</div>
                  </div>
                </CardContent>
              )}
            </Card>
          </StaggerChild>

          {/* Severity + Status side by side */}
          <StaggerChild>
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardContent>
                  <h3 className="text-sm font-medium text-heading mb-3">Severity Distribution</h3>
                  <SeverityBar data={data.alerts_by_severity} />
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <h3 className="text-sm font-medium text-heading mb-3">Alert Status</h3>
                  <div className="space-y-2.5">
                    {Object.entries(data.alerts_by_status).map(([status, count]) => {
                      const total = data.total_alerts || 1
                      const pct = Math.round((count / total) * 100)
                      const colors: Record<string, string> = {
                        new: 'var(--color-info)',
                        in_progress: 'var(--color-warning)',
                        resolved: 'var(--color-success)',
                      }
                      return (
                        <div key={status}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-text capitalize">{status.replace('_', ' ')}</span>
                            <span className="text-xs text-heading font-medium">{count}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-bg overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: colors[status] || 'var(--color-text)',
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          </StaggerChild>

          {/* Partner breakdown (MSSP) */}
          {Object.keys(data.alerts_by_partner).length > 0 && (
            <StaggerChild>
              <Card>
                <CardHeader>
                  <CardTitle>Partners</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2.5">
                    {Object.entries(data.alerts_by_partner)
                      .sort(([, a], [, b]) => b - a)
                      .map(([partner, count]) => {
                        const open = data.open_by_partner[partner] || 0
                        const mttr = data.mttr_by_partner[partner]
                        return (
                          <Link
                            key={partner}
                            to={`/alerts?partner=${encodeURIComponent(partner)}`}
                            className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-surface-hover no-underline transition-colors group"
                          >
                            <div>
                              <div className="text-sm text-heading font-medium group-hover:text-accent transition-colors">{partner}</div>
                              <div className="text-[11px] text-muted">
                                {open > 0 && <span className="text-warning">{open} open</span>}
                                {open > 0 && mttr !== null && mttr !== undefined && ' · '}
                                {mttr !== null && mttr !== undefined && `MTTR ${formatMTTR(mttr)}`}
                              </div>
                            </div>
                            <span className="text-sm text-heading font-semibold">{count}</span>
                          </Link>
                        )
                      })}
                  </div>
                </CardContent>
              </Card>
            </StaggerChild>
          )}
        </StaggerParent>

        {/* Right column — 4/12 */}
        <StaggerParent className="col-span-12 lg:col-span-4 space-y-4">
          {/* My Assignments */}
          {analyst && (
            <StaggerChild>
              <Card>
                <CardHeader className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CardTitle>My Assignments</CardTitle>
                    {hasMyAlerts && (
                      <span className="text-[11px] text-accent bg-accent/10 px-2 py-0.5 rounded-full font-medium">
                        {data.my_alerts.length}
                      </span>
                    )}
                  </div>
                </CardHeader>
                {hasMyAlerts ? (
                  <div className="divide-y divide-border">
                    {data.my_alerts.map((alert) => (
                      <Link
                        key={alert.id}
                        to={`/alerts/${alert.id}`}
                        className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-hover no-underline transition-colors"
                      >
                        <SeverityBadge severity={alert.severity} />
                        <span className="text-sm text-heading flex-1 truncate">{alert.title}</span>
                        <span className="text-[11px] text-muted whitespace-nowrap">{timeAgo(alert.created_at)}</span>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <CardContent>
                    <EmptyState
                      icon={<Shield size={20} />}
                      title="No assignments"
                      description="Claim alerts from the priority queue"
                    />
                  </CardContent>
                )}
              </Card>
            </StaggerChild>
          )}

          {/* Recent Runs */}
          <StaggerChild>
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Recent Runs</CardTitle>
                <Link to="/runs" className="flex items-center gap-1 text-xs text-accent no-underline hover:underline">
                  View all <ArrowRight size={12} />
                </Link>
              </CardHeader>
              {data.recent_runs.length > 0 ? (
                <div className="divide-y divide-border">
                  {data.recent_runs.map((run) => (
                    <Link
                      key={run.id}
                      to={`/runs/${run.id}`}
                      className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-hover no-underline transition-colors"
                    >
                      {run.status === 'success' || run.status === 'completed'
                        ? <CheckCircle size={13} className="text-success shrink-0" />
                        : run.status === 'failed'
                          ? <XCircle size={13} className="text-danger shrink-0" />
                          : <Play size={13} className="text-info shrink-0" />}
                      <span className="text-sm text-heading flex-1 truncate">{run.playbook_id.slice(0, 8)}</span>
                      <StatusBadge status={run.status} />
                      <span className="text-[11px] text-muted whitespace-nowrap">{timeAgo(run.created_at)}</span>
                    </Link>
                  ))}
                </div>
              ) : (
                <CardContent>
                  <div className="text-xs text-muted text-center py-4">No runs yet</div>
                </CardContent>
              )}
            </Card>
          </StaggerChild>
        </StaggerParent>
      </div>
    </PageTransition>
  )
}
