import { cn } from '@/lib/utils'

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div className={cn('animate-pulse rounded-md bg-border/40', className)} style={style} />
  )
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden bg-surface">
      <div className="border-b border-border px-3 py-3 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="border-b border-border last:border-b-0 px-3 py-3.5 flex gap-4">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-3 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="border border-border rounded-lg bg-surface p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3" style={{ width: `${80 - i * 15}%` }} />
      ))}
    </div>
  )
}

export function StatSkeleton() {
  return (
    <div className="border border-border rounded-lg bg-surface p-5">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-5 w-5 rounded" />
      </div>
      <Skeleton className="h-7 w-16" />
    </div>
  )
}
