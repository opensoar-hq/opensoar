import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { LoginPage } from '@/pages/LoginPage'

const login = vi.fn()
const register = vi.fn()

// Stub the AuthContext with a controllable mock so we can assert behavior.
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    analyst: null,
    isLoading: false,
    authCapabilities: {
      local_login_enabled: true,
      local_registration_enabled: true,
      providers: [],
    },
    authCapabilitiesLoading: false,
    login,
    register,
    logout: vi.fn(),
  }),
}))

function getSubmitButton() {
  // The form has two "Sign In" labels (the login/register tab toggle and the
  // form submit). Pick the full-width submit button inside the form.
  const buttons = screen.getAllByRole('button', { name: /sign in/i })
  const submit = buttons.find((b) => b.className.includes('w-full'))
  if (!submit) throw new Error('Submit button not found')
  return submit
}

describe('LoginPage', () => {
  beforeEach(() => {
    login.mockReset()
    register.mockReset()
  })

  it('renders the sign-in form when local login is enabled', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(getSubmitButton()).toBeInTheDocument()
  })

  it('submits username + password through the auth context', async () => {
    login.mockResolvedValue(undefined)
    renderWithProviders(<LoginPage />)

    await userEvent.type(screen.getByLabelText(/username/i), 'alice')
    await userEvent.type(screen.getByLabelText(/password/i), 'secret')
    await userEvent.click(getSubmitButton())

    await waitFor(() => expect(login).toHaveBeenCalledWith('alice', 'secret'))
  })

  it('surfaces "Invalid credentials" when login rejects', async () => {
    login.mockRejectedValue(new Error('401'))
    renderWithProviders(<LoginPage />)

    await userEvent.type(screen.getByLabelText(/username/i), 'alice')
    await userEvent.type(screen.getByLabelText(/password/i), 'bad')
    await userEvent.click(getSubmitButton())

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument()
  })
})
