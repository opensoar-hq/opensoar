import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { RunDetailPage } from '@/pages/RunDetailPage'
import { api, type PlaybookRun } from '@/api'

const run: PlaybookRun = {
  id: 'r-1',
  playbook_id: 'pb-1',
  alert_id: null,
  sequence_id: null,
  sequence_position: null,
  sequence_total: null,
  status: 'completed',
  started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:00:05Z',
  error: null,
  result: null,
  action_results: [
    {
      id: 'step-1',
      action_name: 'lookup_ip',
      status: 'completed',
      started_at: '2026-01-01T00:00:00Z',
      finished_at: '2026-01-01T00:00:01Z',
      duration_ms: 1000,
      input_data: null,
      output_data: null,
      error: null,
      attempt: 1,
    },
    {
      id: 'step-2',
      action_name: 'enrich_domain',
      status: 'failed',
      started_at: '2026-01-01T00:00:01Z',
      finished_at: '2026-01-01T00:00:02Z',
      duration_ms: 1000,
      input_data: null,
      output_data: null,
      error: 'timeout after 30s',
      attempt: 1,
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
}

describe('RunDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api.runs, 'get').mockResolvedValue(run)
    vi.spyOn(api.playbooks, 'list').mockResolvedValue([
      {
        id: 'pb-1',
        name: 'Triage IP',
        description: null,
        partner: null,
        execution_order: 1,
        module_path: '',
        function_name: '',
        trigger_type: null,
        trigger_config: {},
        enabled: true,
        version: 1,
        created_at: '2026-01-01T00:00:00Z',
      },
    ])
  })

  it('renders the playbook name, step count and timeline for the run', async () => {
    renderWithProviders(<RunDetailPage />, {
      initialEntries: ['/runs/r-1'],
      routePath: '/runs/:id',
    })

    expect(await screen.findByText('Triage IP')).toBeInTheDocument()
    expect(await screen.findByText('lookup_ip')).toBeInTheDocument()
    expect(screen.getByText('enrich_domain')).toBeInTheDocument()
    // The failed step auto-expands so the error text should be visible
    expect(screen.getByText('timeout after 30s')).toBeInTheDocument()
  })

  it('shows "Run not found" when the API returns no data', async () => {
    vi.spyOn(api.runs, 'get').mockResolvedValue(
      undefined as unknown as PlaybookRun,
    )

    renderWithProviders(<RunDetailPage />, {
      initialEntries: ['/runs/missing'],
      routePath: '/runs/:id',
    })

    expect(await screen.findByText('Run not found')).toBeInTheDocument()
  })
})
