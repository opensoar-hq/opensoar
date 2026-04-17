import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { IncidentDetailPage } from '@/pages/IncidentDetailPage'
import { api, type Alert, type Incident2 } from '@/api'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    analyst: {
      id: 'analyst-1',
      username: 'alice',
      display_name: 'Alice',
      email: null,
      is_active: true,
      has_local_password: true,
      role: 'admin',
      created_at: '2026-01-01T00:00:00Z',
    },
    isLoading: false,
    authCapabilities: { local_login_enabled: true, local_registration_enabled: false, providers: [] },
    authCapabilitiesLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}))

const incident: Incident2 = {
  id: 'inc-1',
  title: 'Lateral movement detected',
  description: 'Suspicious RDP activity',
  severity: 'high',
  status: 'open',
  assigned_to: null,
  assigned_username: null,
  tags: ['rdp'],
  alert_count: 1,
  closed_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const alertOne: Alert = {
  id: 'alrt-1',
  source: 'elastic',
  source_id: null,
  title: 'RDP brute force',
  description: null,
  severity: 'high',
  status: 'new',
  source_ip: '10.0.0.1',
  dest_ip: null,
  hostname: null,
  rule_name: null,
  iocs: null,
  tags: null,
  assigned_to: null,
  assigned_username: null,
  duplicate_count: 1,
  partner: null,
  determination: 'unknown',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('IncidentDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api.incidents, 'get').mockResolvedValue(incident)
    vi.spyOn(api.incidents, 'alerts').mockResolvedValue([alertOne])
    vi.spyOn(api.incidents, 'activities').mockResolvedValue({ activities: [], total: 0 })
    vi.spyOn(api.incidents, 'observables').mockResolvedValue([])
    vi.spyOn(api.analysts, 'list').mockResolvedValue([])
  })

  it('renders the incident title, description and linked alert', async () => {
    renderWithProviders(<IncidentDetailPage />, {
      initialEntries: ['/incidents/inc-1'],
      routePath: '/incidents/:id',
    })

    expect(await screen.findByText('Lateral movement detected')).toBeInTheDocument()
    expect(screen.getByText('Suspicious RDP activity')).toBeInTheDocument()
    expect(await screen.findByText('RDP brute force')).toBeInTheDocument()
  })

  it('calls the API to link an alert when a new id is submitted', async () => {
    const linkSpy = vi
      .spyOn(api.incidents, 'linkAlert')
      .mockResolvedValue({ detail: 'linked' })

    renderWithProviders(<IncidentDetailPage />, {
      initialEntries: ['/incidents/inc-1'],
      routePath: '/incidents/:id',
    })

    await screen.findByText('Lateral movement detected')
    const openDialogButtons = screen.getAllByRole('button', { name: /link alert/i })
    await userEvent.click(openDialogButtons[0])

    await userEvent.type(
      await screen.findByPlaceholderText(/paste alert id/i),
      'alrt-2',
    )

    // The dialog footer button also says "Link Alert" — pick the one inside
    // the dialog itself so we don't re-open the dialog.
    const submitButtons = screen.getAllByRole('button', { name: /link alert/i })
    await userEvent.click(submitButtons[submitButtons.length - 1])

    await waitFor(() => {
      expect(linkSpy).toHaveBeenCalledWith('inc-1', 'alrt-2')
    })
  })

  it('calls the API to unlink an alert when its unlink button is pressed', async () => {
    const unlinkSpy = vi
      .spyOn(api.incidents, 'unlinkAlert')
      .mockResolvedValue({ detail: 'unlinked' })

    renderWithProviders(<IncidentDetailPage />, {
      initialEntries: ['/incidents/inc-1'],
      routePath: '/incidents/:id',
    })

    await screen.findByText('RDP brute force')
    await userEvent.click(screen.getByTitle('Unlink alert'))

    await waitFor(() => {
      expect(unlinkSpy).toHaveBeenCalledWith('inc-1', 'alrt-1')
    })
  })
})
