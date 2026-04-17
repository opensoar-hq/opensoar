import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { api, type Analyst, type AuthCapabilities } from '@/api'

const analyst: Analyst = {
  id: 'a-1',
  username: 'alice',
  display_name: 'Alice',
  email: null,
  is_active: true,
  has_local_password: true,
  role: 'admin',
  created_at: '2026-01-01T00:00:00Z',
}

const capabilities: AuthCapabilities = {
  local_login_enabled: true,
  local_registration_enabled: true,
  providers: [],
}

function AuthConsumer() {
  const { analyst, isLoading, login, logout, authCapabilitiesLoading } = useAuth()
  return (
    <div>
      <div data-testid="loading">{String(isLoading)}</div>
      <div data-testid="caps-loading">{String(authCapabilitiesLoading)}</div>
      <div data-testid="username">{analyst?.username ?? 'anon'}</div>
      <div data-testid="role">{analyst?.role ?? ''}</div>
      <button onClick={() => login('alice', 'pw')}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.spyOn(api.auth, 'capabilities').mockResolvedValue(capabilities)
  })

  it('starts with no analyst when no token is persisted', async () => {
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('caps-loading')).toHaveTextContent('false'))
    expect(screen.getByTestId('username')).toHaveTextContent('anon')
    expect(screen.getByTestId('loading')).toHaveTextContent('false')
  })

  it('persists the token after login and exposes the analyst', async () => {
    const loginSpy = vi.spyOn(api.auth, 'login').mockResolvedValue({
      access_token: 'tok-123',
      token_type: 'bearer',
      analyst,
    })

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('caps-loading')).toHaveTextContent('false'))
    await userEvent.click(screen.getByText('login'))

    await waitFor(() => expect(screen.getByTestId('username')).toHaveTextContent('alice'))
    expect(screen.getByTestId('role')).toHaveTextContent('admin')
    expect(localStorage.getItem('opensoar_token')).toBe('tok-123')
    expect(loginSpy).toHaveBeenCalledWith({ username: 'alice', password: 'pw' })
  })

  it('clears the token and analyst on logout', async () => {
    vi.spyOn(api.auth, 'login').mockResolvedValue({
      access_token: 'tok-xyz',
      token_type: 'bearer',
      analyst,
    })
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('caps-loading')).toHaveTextContent('false'))
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(localStorage.getItem('opensoar_token')).toBe('tok-xyz'))

    await userEvent.click(screen.getByText('logout'))
    expect(localStorage.getItem('opensoar_token')).toBeNull()
    expect(screen.getByTestId('username')).toHaveTextContent('anon')
  })

  it('rehydrates analyst from persisted token on mount', async () => {
    localStorage.setItem('opensoar_token', 'persisted-token')
    vi.spyOn(api.auth, 'me').mockResolvedValue(analyst)

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('username')).toHaveTextContent('alice'))
    expect(screen.getByTestId('loading')).toHaveTextContent('false')
  })

  it('clears an invalid persisted token when /auth/me fails', async () => {
    localStorage.setItem('opensoar_token', 'stale-token')
    vi.spyOn(api.auth, 'me').mockRejectedValue(new Error('401'))

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
    expect(localStorage.getItem('opensoar_token')).toBeNull()
    expect(screen.getByTestId('username')).toHaveTextContent('anon')
  })

  it('throws when useAuth is used outside the provider', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => {
      act(() => {
        render(<AuthConsumer />)
      })
    }).toThrow(/AuthProvider/)
    errSpy.mockRestore()
  })
})
