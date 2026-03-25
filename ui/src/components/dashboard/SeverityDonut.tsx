import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#da3633',
  high: '#f85149',
  medium: '#d29922',
  low: '#848d97',
}

const ORDER = ['critical', 'high', 'medium', 'low']

interface Props {
  data: Record<string, number>
}

export function SeverityDonut({ data }: Props) {
  const total = Object.values(data).reduce((a, b) => a + b, 0)
  if (total === 0) return <div className="text-xs text-muted text-center py-6">No alerts</div>

  const entries = ORDER
    .filter((sev) => (data[sev] || 0) > 0)
    .map((sev) => ({ name: sev, value: data[sev] || 0 }))

  return (
    <div className="flex items-center gap-4">
      <div className="w-[130px] h-[130px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={entries}
              cx="50%"
              cy="50%"
              innerRadius={36}
              outerRadius={58}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
            >
              {entries.map((e) => (
                <Cell key={e.name} fill={SEVERITY_COLORS[e.name]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: '#161b22',
                border: '1px solid #30363d',
                borderRadius: 6,
                fontSize: 12,
                color: '#e6edf3',
              }}
              formatter={(value, name) => [String(value), String(name)]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-2 flex-1 min-w-0">
        {ORDER.map((sev) => {
          const count = data[sev] || 0
          const pct = total > 0 ? Math.round((count / total) * 100) : 0
          return (
            <div key={sev} className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: SEVERITY_COLORS[sev] }} />
              <span className="text-xs text-muted capitalize flex-1">{sev}</span>
              <span className="text-xs text-heading font-medium tabular-nums">{count}</span>
              <span className="text-[10px] text-muted tabular-nums w-8 text-right">{pct}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
