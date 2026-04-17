import type { ReactElement, ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router'
import { render, type RenderOptions } from '@testing-library/react'
import { ToastProvider } from '@/components/ui/Toast'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

interface TestProviderOptions {
  initialEntries?: string[]
  routePath?: string
  queryClient?: QueryClient
  withToast?: boolean
}

export function renderWithProviders(
  ui: ReactElement,
  {
    initialEntries = ['/'],
    routePath,
    queryClient = createTestQueryClient(),
    withToast = true,
    ...rtlOptions
  }: TestProviderOptions & Omit<RenderOptions, 'wrapper'> = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    const routed = routePath ? (
      <Routes>
        <Route path={routePath} element={children} />
      </Routes>
    ) : (
      children
    )

    const withinToast = withToast ? <ToastProvider>{routed}</ToastProvider> : routed

    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>{withinToast}</MemoryRouter>
      </QueryClientProvider>
    )
  }

  return {
    queryClient,
    ...render(ui, { wrapper: Wrapper, ...rtlOptions }),
  }
}
