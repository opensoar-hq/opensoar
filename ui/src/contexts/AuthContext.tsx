/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { api, onUnauthorized, type Analyst, type AuthCapabilities } from '@/api'

interface AuthContextType {
  analyst: Analyst | null
  isLoading: boolean
  authCapabilities: AuthCapabilities
  authCapabilitiesLoading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, displayName: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)
const DEFAULT_AUTH_CAPABILITIES: AuthCapabilities = {
  local_login_enabled: true,
  local_registration_enabled: false,
  providers: [],
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [initialToken] = useState(() => localStorage.getItem('opensoar_token'))
  const [analyst, setAnalyst] = useState<Analyst | null>(null)
  const [isLoading, setIsLoading] = useState(() => Boolean(initialToken))
  const [authCapabilities, setAuthCapabilities] = useState<AuthCapabilities>(DEFAULT_AUTH_CAPABILITIES)
  const [authCapabilitiesLoading, setAuthCapabilitiesLoading] = useState(true)

  useEffect(() => {
    api.auth.capabilities()
      .then(setAuthCapabilities)
      .catch(() => {
        setAuthCapabilities(DEFAULT_AUTH_CAPABILITIES)
      })
      .finally(() => setAuthCapabilitiesLoading(false))

    if (initialToken) {
      api.auth.me()
        .then(setAnalyst)
        .catch(() => {
          localStorage.removeItem('opensoar_token')
          setAnalyst(null)
        })
        .finally(() => setIsLoading(false))
    }
  }, [initialToken])

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.auth.login({ username, password })
    localStorage.setItem('opensoar_token', res.access_token)
    setAnalyst(res.analyst)
  }, [])

  const register = useCallback(async (username: string, displayName: string, password: string) => {
    const res = await api.auth.register({ username, display_name: displayName, password })
    localStorage.setItem('opensoar_token', res.access_token)
    setAnalyst(res.analyst)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('opensoar_token')
    setAnalyst(null)
  }, [])

  // Any 401 from api.ts clears the session — RequireAuth then redirects to /login.
  useEffect(() => {
    return onUnauthorized(() => {
      localStorage.removeItem('opensoar_token')
      setAnalyst(null)
    })
  }, [])

  return (
    <AuthContext.Provider value={{ analyst, isLoading, authCapabilities, authCapabilitiesLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
