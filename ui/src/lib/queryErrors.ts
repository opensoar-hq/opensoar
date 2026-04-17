import { QueryCache, MutationCache, QueryClient } from '@tanstack/react-query'
import { classifyError } from '@/lib/errors'
import type { useToast } from '@/components/ui/Toast'

type ToastApi = ReturnType<typeof useToast>

interface BuildOptions {
  toast: ToastApi
}

/**
 * Build a shared QueryClient wired to the toast system.
 *
 * - GET query failures classified as `server` or `network` show a toast with
 *   a Retry action that re-invokes `query.fetch()`.
 * - 401 is silent (handled via api.ts -> AuthProvider, which redirects).
 * - 422 is silent at the toast layer; the page renders inline field errors
 *   from `error.body.detail` using `classifyError(err).fieldErrors`.
 * - Mutations default to toast-on-error so callers that forget a local
 *   `onError` still get a reasonable message. Local `onError` handlers
 *   still run and can be more specific (e.g. field errors on forms).
 */
export function buildQueryClient({ toast }: BuildOptions): QueryClient {
  const queryCache = new QueryCache({
    onError: (error, query) => {
      const cat = classifyError(error)
      if (!cat.shouldToast) return
      // Only show retry on queries (GETs). Mutations handle their own retry.
      if (cat.kind === 'server' || cat.kind === 'network') {
        toast.error(
          cat.kind === 'network' ? 'Network error' : 'Server error',
          cat.message,
          {
            action: {
              label: 'Retry',
              onClick: () => { void query.fetch() },
            },
          },
        )
        return
      }
      toast.error('Request failed', cat.message)
    },
  })

  const mutationCache = new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      // If the caller attached its own onError, let that drive the UX
      // (typically inline field errors for validation cases).
      if (mutation.options.onError) return
      const cat = classifyError(error)
      if (!cat.shouldToast) return
      toast.error(
        cat.kind === 'network' ? 'Network error' : 'Request failed',
        cat.message,
      )
    },
  })

  return new QueryClient({
    queryCache,
    mutationCache,
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 1 },
    },
  })
}
