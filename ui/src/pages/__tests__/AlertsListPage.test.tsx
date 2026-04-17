import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { AlertsListPage } from '@/pages/AlertsListPage'
import { api, type Alert } from '@/api'

// WorkspaceContext depends on AuthContext + an API call; stub it out so we
// can render the page in isolation.
vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({ selectedTenantId: '', setSelectedTenantId: () => {}, tenants: [] }),
}))

function makeAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: overrides.id ?? 'a-1',
    source: 'elastic',
    source_id: null,
    title: overrides.title ?? 'Suspicious login',
    description: null,
    severity: overrides.severity ?? 'high',
    status: overrides.status ?? 'new',
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
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('AlertsListPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the list of alerts returned by the API', async () => {
    vi.spyOn(api.alerts, 'list').mockResolvedValue({
      alerts: [
        makeAlert({ id: 'a-1', title: 'Phishing email detected' }),
        makeAlert({ id: 'a-2', title: 'Malware hash matched', severity: 'critical' }),
      ],
      total: 2,
    })

    renderWithProviders(<AlertsListPage />)

    expect(await screen.findByText('Phishing email detected')).toBeInTheDocument()
    expect(screen.getByText('Malware hash matched')).toBeInTheDocument()
  })

  it('shows the empty-state when the API returns no alerts', async () => {
    vi.spyOn(api.alerts, 'list').mockResolvedValue({ alerts: [], total: 0 })

    renderWithProviders(<AlertsListPage />)

    expect(await screen.findByText('No alerts found')).toBeInTheDocument()
  })

  it('filters alerts client-side using the search box', async () => {
    vi.spyOn(api.alerts, 'list').mockResolvedValue({
      alerts: [
        makeAlert({ id: 'a-1', title: 'Phishing email detected' }),
        makeAlert({ id: 'a-2', title: 'Malware hash matched' }),
      ],
      total: 2,
    })

    renderWithProviders(<AlertsListPage />)

    await screen.findByText('Phishing email detected')
    await userEvent.type(screen.getByPlaceholderText(/search alerts/i), 'phishing')

    await waitFor(() => {
      expect(screen.getByText('Phishing email detected')).toBeInTheDocument()
      expect(screen.queryByText('Malware hash matched')).not.toBeInTheDocument()
    })
  })
})
