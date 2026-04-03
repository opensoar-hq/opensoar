import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Input, Label } from '@/components/ui/Input'

const ease = [0.25, 0.1, 0.25, 1] as [number, number, number, number]

export function LoginPage() {
  const { login, register, authCapabilities, authCapabilitiesLoading } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const canLoginLocally = authCapabilities.local_login_enabled
  const canRegisterLocally = authCapabilities.local_registration_enabled
  const hasExternalProviders = authCapabilities.providers.length > 0

  useEffect(() => {
    if (mode === 'register' && !canRegisterLocally) {
      setMode('login')
    }
    if (mode === 'login' && !canLoginLocally && canRegisterLocally) {
      setMode('register')
    }
  }, [canLoginLocally, canRegisterLocally, mode])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(username, password)
      } else {
        await register(username, displayName || username, password)
      }
    } catch {
      setError(mode === 'login' ? 'Invalid credentials' : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const handleProviderSignIn = (loginUrl: string | null) => {
    if (!loginUrl) return
    window.location.assign(loginUrl)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <motion.div
        className="w-full max-w-sm px-4"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease }}
      >
        <motion.div
          className="text-center mb-10"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4, ease }}
        >
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-accent/15 border border-accent/30 mb-4">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h1 className="text-2xl text-heading" style={{ fontFamily: "'Inter Tight', sans-serif", letterSpacing: '-0.03em' }}><span style={{ fontWeight: 400 }}>Open</span><span style={{ fontWeight: 700 }}>SOAR</span></h1>
          <p className="text-sm text-muted mt-1">Security Orchestration, Automation & Response</p>
        </motion.div>

        <motion.div
          className="relative"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4, ease }}
        >
          {/* Subtle glow behind card */}
          <div className="absolute -inset-1 bg-gradient-to-b from-accent/10 via-accent/5 to-transparent rounded-2xl blur-xl pointer-events-none" />

          <Card className="relative shadow-lg shadow-black/20">
            <CardContent className="p-6">
              {canLoginLocally || canRegisterLocally ? (
                <div className="flex gap-0 mb-6 border border-border rounded-lg overflow-hidden bg-bg">
                  {canLoginLocally ? (
                    <button
                      type="button"
                      onClick={() => setMode('login')}
                      className={`flex-1 py-2.5 text-xs font-medium border-none cursor-pointer transition-all duration-200 ${
                        mode === 'login'
                          ? 'bg-heading text-bg shadow-sm'
                          : 'bg-transparent text-muted hover:text-heading'
                      }`}
                    >
                      Sign In
                    </button>
                  ) : null}
                  {canRegisterLocally ? (
                    <button
                      type="button"
                      onClick={() => setMode('register')}
                      className={`flex-1 py-2.5 text-xs font-medium border-none cursor-pointer transition-all duration-200 ${
                        mode === 'register'
                          ? 'bg-heading text-bg shadow-sm'
                          : 'bg-transparent text-muted hover:text-heading'
                      }`}
                    >
                      Register
                    </button>
                  ) : null}
                </div>
              ) : null}

              {hasExternalProviders ? (
                <div className="mb-6 space-y-3">
                  {authCapabilities.providers.map((provider) => (
                    <Button
                      key={provider.id}
                      type="button"
                      variant="default"
                      size="lg"
                      className="w-full justify-center"
                      onClick={() => handleProviderSignIn(provider.login_url)}
                      disabled={!provider.login_url || loading}
                    >
                      Continue with {provider.name}
                    </Button>
                  ))}
                  {(canLoginLocally || canRegisterLocally) ? (
                    <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.18em] text-muted/70">
                      <div className="h-px flex-1 bg-border" />
                      <span>or</span>
                      <div className="h-px flex-1 bg-border" />
                    </div>
                  ) : null}
                </div>
              ) : null}

              {(canLoginLocally || canRegisterLocally) ? (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="analyst"
                      required
                    />
                  </div>

                  {mode === 'register' && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2, ease }}
                    >
                      <Label htmlFor="displayName">Display Name</Label>
                      <Input
                        id="displayName"
                        type="text"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder="Jane Doe"
                      />
                    </motion.div>
                  )}

                  <div>
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                    />
                  </div>

                  {error && (
                    <motion.div
                      className="flex items-center gap-2 text-xs text-danger bg-danger/10 border border-danger/20 rounded-md px-3 py-2.5"
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="15" y1="9" x2="9" y2="15" />
                        <line x1="9" y1="9" x2="15" y2="15" />
                      </svg>
                      {error}
                    </motion.div>
                  )}

                  <Button
                    variant="primary"
                    size="lg"
                    className="w-full justify-center mt-2"
                    disabled={loading || !username || !password}
                  >
                    {loading ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Please wait...
                      </>
                    ) : mode === 'login' ? 'Sign In' : 'Create Account'}
                  </Button>
                </form>
              ) : !hasExternalProviders ? (
                <div className="rounded-md border border-border bg-bg px-4 py-3 text-sm text-muted">
                  {authCapabilitiesLoading
                    ? 'Loading sign-in options...'
                    : 'No local sign-in methods are enabled for this deployment.'}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>

        <motion.p
          className="text-[11px] text-muted/60 text-center mt-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.3 }}
        >
          Open-source SOAR platform
        </motion.p>
      </motion.div>
    </div>
  )
}
