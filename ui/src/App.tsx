import { useMemo } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { WorkspaceProvider } from '@/contexts/WorkspaceContext'
import { ToastProvider, useToast } from '@/components/ui/Toast'
import { AppLayout } from '@/layouts/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { AlertsListPage } from '@/pages/AlertsListPage'
import { AlertDetailPage } from '@/pages/AlertDetailPage'
import { RunsListPage } from '@/pages/RunsListPage'
import { RunDetailPage } from '@/pages/RunDetailPage'
import { PlaybooksListPage } from '@/pages/PlaybooksListPage'
import { IncidentsListPage } from '@/pages/IncidentsListPage'
import { IncidentDetailPage } from '@/pages/IncidentDetailPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { LoginPage } from '@/pages/LoginPage'
import { Spinner } from '@/components/ui/Spinner'
import { buildQueryClient } from '@/lib/queryErrors'

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

function AppRoutes() {
  const toast = useToast()
  // Build the QueryClient once we have toast available — so global query and
  // mutation errors can surface through the unified toast system.
  const queryClient = useMemo(() => buildQueryClient({ toast }), [toast])
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WorkspaceProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
              <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
                <Route index element={<DashboardPage />} />
                <Route path="alerts" element={<AlertsListPage />} />
                <Route path="alerts/:id" element={<AlertDetailPage />} />
                <Route path="runs" element={<RunsListPage />} />
                <Route path="runs/:id" element={<RunDetailPage />} />
                <Route path="incidents" element={<IncidentsListPage />} />
                <Route path="incidents/:id" element={<IncidentDetailPage />} />
                <Route path="playbooks" element={<PlaybooksListPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </WorkspaceProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AppRoutes />
    </ToastProvider>
  )
}
