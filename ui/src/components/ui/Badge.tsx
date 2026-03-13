import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  color?: string
  className?: string
}

export function Badge({ children, color, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wide whitespace-nowrap',
        className,
      )}
      style={color ? {
        backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
      } : undefined}
    >
      {children}
    </span>
  )
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--color-critical)',
  high: 'var(--color-danger)',
  medium: 'var(--color-warning)',
  low: 'var(--color-info)',
}

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge color={SEVERITY_COLORS[severity] || 'var(--color-text)'}>{severity}</Badge>
}

const STATUS_COLORS: Record<string, string> = {
  new: 'var(--color-info)',
  in_progress: 'var(--color-warning)',
  resolved: 'var(--color-success)',
  // Legacy — keep for runs
  closed: 'var(--color-muted)',
  success: 'var(--color-success)',
  completed: 'var(--color-success)',
  failed: 'var(--color-danger)',
  running: 'var(--color-info)',
  pending: 'var(--color-muted)',
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge color={STATUS_COLORS[status] || 'var(--color-text)'}>{status.replace('_', ' ')}</Badge>
}

const DETERMINATION_COLORS: Record<string, string> = {
  unknown: 'var(--color-muted)',
  malicious: 'var(--color-danger)',
  suspicious: 'var(--color-warning)',
  benign: 'var(--color-success)',
}

export function DeterminationBadge({ determination }: { determination: string }) {
  return <Badge color={DETERMINATION_COLORS[determination] || 'var(--color-text)'}>{determination}</Badge>
}
