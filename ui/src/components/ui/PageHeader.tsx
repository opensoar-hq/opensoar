import type { ReactNode } from 'react'

export function PageHeader({ icon, title, count, children }: {
  icon: ReactNode
  title: string
  count?: number
  children?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-2">
        <span className="text-muted">{icon}</span>
        <h1 className="text-base font-semibold text-heading m-0">{title}</h1>
        {count !== undefined && (
          <span className="text-xs text-muted">({count})</span>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
