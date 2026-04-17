import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { IncidentsListPage } from '@/pages/IncidentsListPage'
import { api, type Incident2 } from '@/api'

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({ selectedTenantId: '', setSelectedTenantId: () => {}, tenants: [] }),
}))

function makeIncident(overrides: Partial<Incident2> = {}): Incident2 {
  return {
    id: 'i-1',
    title: 'Lateral movement',
    description: null,
    severity: 'high',
    status: 'open',
    assigned_to: null,
    assigned_username: null,
    tags: null,
    alert_count: 3,
    closed_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('IncidentsListPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api.incidents, 'suggestions').mockResolvedValue([])
  })

  it('renders incidents from the API', async () => {
    vi.spyOn(api.incidents, 'list').mockResolvedValue({
      incidents: [
        makeIncident({ id: 'i-1', title: 'Brute force on VPN' }),
        makeIncident({ id: 'i-2', title: 'Data exfiltration attempt', severity: 'critical' }),
      ],
      total: 2,
    })

    renderWithProviders(<IncidentsListPage />)

    expect(await screen.findByText('Brute force on VPN')).toBeInTheDocument()
    expect(screen.getByText('Data exfiltration attempt')).toBeInTheDocument()
  })

  it('renders the empty-state when there are no incidents', async () => {
    vi.spyOn(api.incidents, 'list').mockResolvedValue({ incidents: [], total: 0 })

    renderWithProviders(<IncidentsListPage />)

    expect(await screen.findByText('No incidents found')).toBeInTheDocument()
  })

  it('renders the correlation suggestions panel when suggestions are returned', async () => {
    vi.spyOn(api.incidents, 'list').mockResolvedValue({ incidents: [], total: 0 })
    vi.spyOn(api.incidents, 'suggestions').mockResolvedValue([
      {
        source_ip: '10.0.0.1',
        alert_count: 2,
        alerts: [
          {
            id: 'a-1',
            source: 's',
            source_id: null,
            title: 'Brute force from 10.0.0.1',
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
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
      },
    ])

    renderWithProviders(<IncidentsListPage />)

    expect(await screen.findByText('Correlation Suggestions')).toBeInTheDocument()
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument()
  })
})
