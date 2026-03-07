import type { ReactNode } from 'react'

export function EmptyState({ icon, title, description }: { icon: ReactNode; title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 border border-border rounded-lg bg-surface">
      <div className="text-muted mb-3">{icon}</div>
      <h3 className="text-sm font-medium text-heading mb-1">{title}</h3>
      {description && <p className="text-xs text-muted">{description}</p>}
    </div>
  )
}
