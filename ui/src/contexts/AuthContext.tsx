import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { api, type Analyst } from '@/api'

interface AuthContextType {
  analyst: Analyst | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, displayName: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [analyst, setAnalyst] = useState<Analyst | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('opensoar_token')
    if (token) {
      api.auth.me()
        .then(setAnalyst)
        .catch(() => {
          localStorage.removeItem('opensoar_token')
          setAnalyst(null)
        })
        .finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [])

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

  return (
    <AuthContext.Provider value={{ analyst, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
