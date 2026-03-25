import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface Alert {
  created_at: string
  severity: string
}

interface Props {
  alerts: Alert[]
}

function bucketByDay(alerts: Alert[], days: number): { label: string; count: number; critical: number }[] {
  const now = new Date()
  const buckets: Map<string, { count: number; critical: number }> = new Map()

  // Initialise last N days
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(5, 10) // MM-DD
    buckets.set(key, { count: 0, critical: 0 })
  }

  for (const a of alerts) {
    const key = a.created_at.slice(5, 10)
    const bucket = buckets.get(key)
    if (bucket) {
      bucket.count++
      if (a.severity === 'critical' || a.severity === 'high') {
        bucket.critical++
      }
    }
  }

  return Array.from(buckets.entries()).map(([label, v]) => ({
    label,
    count: v.count,
    critical: v.critical,
  }))
}

export function ActivitySparkline({ alerts }: Props) {
  const data = bucketByDay(alerts, 14)
  const hasData = data.some((d) => d.count > 0)

  if (!hasData) {
    return <div className="text-xs text-muted text-center py-6">No recent activity</div>
  }

  return (
    <div className="h-[140px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="alertGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f85149" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f85149" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="critGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#da3633" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#da3633" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#30363d" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: '#6e7681' }}
            axisLine={{ stroke: '#30363d' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#6e7681' }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              background: '#161b22',
              border: '1px solid #30363d',
              borderRadius: 6,
              fontSize: 12,
              color: '#e6edf3',
            }}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Area
            type="monotone"
            dataKey="count"
            name="All alerts"
            stroke="#f85149"
            strokeWidth={1.5}
            fill="url(#alertGrad)"
          />
          <Area
            type="monotone"
            dataKey="critical"
            name="Critical/High"
            stroke="#da3633"
            strokeWidth={1.5}
            fill="url(#critGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
