import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { ToastProvider } from '@/components/ui/Toast'
import { AppLayout } from '@/layouts/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { AlertsListPage } from '@/pages/AlertsListPage'
import { AlertDetailPage } from '@/pages/AlertDetailPage'
import { RunsListPage } from '@/pages/RunsListPage'
import { RunDetailPage } from '@/pages/RunDetailPage'
import { PlaybooksListPage } from '@/pages/PlaybooksListPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { LoginPage } from '@/pages/LoginPage'
import { Spinner } from '@/components/ui/Spinner'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { analyst, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <Spinner size={24} />
      </div>
    )
  }

  if (!analyst) {
    return <Navigate to="/login" replace />
  }

  return children
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { analyst, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <Spinner size={24} />
      </div>
    )
  }

  if (analyst) {
    return <Navigate to="/" replace />
  }

  return children
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
              <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
                <Route index element={<DashboardPage />} />
                <Route path="alerts" element={<AlertsListPage />} />
                <Route path="alerts/:id" element={<AlertDetailPage />} />
                <Route path="runs" element={<RunsListPage />} />
                <Route path="runs/:id" element={<RunDetailPage />} />
                <Route path="playbooks" element={<PlaybooksListPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
