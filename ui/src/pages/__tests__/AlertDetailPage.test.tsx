import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { AlertDetailPage } from '@/pages/AlertDetailPage'
import { api, type AlertDetail } from '@/api'

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

const detail: AlertDetail = {
  id: 'alrt-1',
  source: 'elastic',
  source_id: null,
  title: 'Phishing email detected',
  description: 'User clicked on a suspicious link',
  severity: 'high',
  status: 'new',
  source_ip: '10.0.0.1',
  dest_ip: null,
  hostname: 'host-01',
  rule_name: 'phish-rule',
  iocs: null,
  tags: null,
  assigned_to: null,
  assigned_username: null,
  duplicate_count: 1,
  partner: null,
  determination: 'unknown',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  raw_payload: {},
  normalized: {},
  resolved_at: null,
  resolve_reason: null,
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api.alerts, 'get').mockResolvedValue(detail)
    vi.spyOn(api.alerts, 'getRuns').mockResolvedValue({ runs: [], total: 0 })
    vi.spyOn(api.alerts, 'getIncidents').mockResolvedValue([])
    vi.spyOn(api.alerts, 'getActivities').mockResolvedValue({ activities: [], total: 0 })
    vi.spyOn(api.playbooks, 'list').mockResolvedValue([])
    vi.spyOn(api.actions, 'available').mockResolvedValue([])
    vi.spyOn(api.analysts, 'list').mockResolvedValue([])
  })

  it('renders the alert detail title and description', async () => {
    renderWithProviders(<AlertDetailPage />, {
      initialEntries: ['/alerts/alrt-1'],
      routePath: '/alerts/:id',
    })

    expect(await screen.findByText('Phishing email detected')).toBeInTheDocument()
    expect(screen.getByText('User clicked on a suspicious link')).toBeInTheDocument()
  })

  it('renders "Alert not found" when the API returns nothing', async () => {
    vi.spyOn(api.alerts, 'get').mockResolvedValue(
      undefined as unknown as AlertDetail,
    )

    renderWithProviders(<AlertDetailPage />, {
      initialEntries: ['/alerts/missing'],
      routePath: '/alerts/:id',
    })

    expect(await screen.findByText('Alert not found')).toBeInTheDocument()
  })
})
