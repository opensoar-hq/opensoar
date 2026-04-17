import { AlertTriangle, RotateCw } from 'lucide-react'
import { classifyError } from '@/lib/errors'
import { Button } from '@/components/ui/Button'

interface QueryErrorStateProps {
  error: unknown
  onRetry: () => void
  title?: string
  className?: string
}

/**
 * Inline error block for non-destructive GET queries. Pair with
 * `query.isError` + `query.refetch` from React Query.
 */
export function QueryErrorState({ error, onRetry, title, className }: QueryErrorStateProps) {
  const cat = classifyError(error)
  const heading =
    title ?? (cat.kind === 'network' ? 'Could not reach the server' : 'Something went wrong')

  return (
    <div
      className={
        'flex flex-col items-center justify-center text-center gap-3 rounded-md border border-danger/20 bg-danger/5 px-6 py-8 ' +
        (className ?? '')
      }
      role="alert"
    >
      <AlertTriangle size={20} className="text-danger" />
      <div>
        <div className="text-sm font-medium text-heading">{heading}</div>
        <div className="text-xs text-muted mt-1 max-w-md">{cat.message}</div>
      </div>
      <Button variant="default" size="sm" onClick={onRetry}>
        <RotateCw size={12} className="mr-1.5" />
        Retry
      </Button>
    </div>
  )
}
