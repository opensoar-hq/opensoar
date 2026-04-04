/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api, type TenantInfo } from '@/api'
import { useAuth } from '@/contexts/AuthContext'

interface WorkspaceContextType {
  tenants: TenantInfo[]
  selectedTenantId: string
  setSelectedTenantId: (tenantId: string) => void
}

const STORAGE_KEY = 'opensoar_active_tenant'
const WorkspaceContext = createContext<WorkspaceContextType | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { analyst } = useAuth()
  const [selectedTenantIdState, setSelectedTenantIdState] = useState(
    () => localStorage.getItem(STORAGE_KEY) ?? '',
  )

  const { data: tenants = [] } = useQuery({
    queryKey: ['workspace-tenants', analyst?.id],
    queryFn: api.tenants.list,
    enabled: Boolean(analyst),
    retry: false,
  })

  const selectedTenantId = useMemo(() => {
    if (!selectedTenantIdState) return ''
    return tenants.some((tenant) => tenant.id === selectedTenantIdState) ? selectedTenantIdState : ''
  }, [selectedTenantIdState, tenants])

  useEffect(() => {
    if (selectedTenantId) {
      localStorage.setItem(STORAGE_KEY, selectedTenantId)
      return
    }
    localStorage.removeItem(STORAGE_KEY)
  }, [selectedTenantId])

  return (
    <WorkspaceContext.Provider
      value={{
        tenants,
        selectedTenantId,
        setSelectedTenantId: setSelectedTenantIdState,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return ctx
}
