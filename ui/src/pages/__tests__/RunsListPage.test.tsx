import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { RunsListPage } from '@/pages/RunsListPage'
import { api, type PlaybookRun } from '@/api'

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({ selectedTenantId: '', setSelectedTenantId: () => {}, tenants: [] }),
}))

function makeRun(overrides: Partial<PlaybookRun> = {}): PlaybookRun {
  return {
    id: overrides.id ?? 'r-1',
    playbook_id: overrides.playbook_id ?? 'pb-1',
    alert_id: null,
    sequence_id: null,
    sequence_position: null,
    sequence_total: null,
    status: overrides.status ?? 'completed',
    started_at: '2026-01-01T00:00:00Z',
    finished_at: '2026-01-01T00:00:01Z',
    error: null,
    result: null,
    action_results: overrides.action_results ?? [],
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('RunsListPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
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

  it('renders the runs returned by the API with playbook names', async () => {
    vi.spyOn(api.runs, 'list').mockResolvedValue({
      runs: [makeRun({ id: 'r-1' }), makeRun({ id: 'r-2', status: 'failed' })],
      total: 2,
    })

    renderWithProviders(<RunsListPage />)

    // Row labels use <span>. The filter Select also renders <option> with the
    // same text, so count just the row spans.
    await screen.findAllByText('Triage IP')
    const rowLabels = screen
      .getAllByText('Triage IP')
      .filter((el) => el.tagName.toLowerCase() === 'span')
    expect(rowLabels.length).toBe(2)
  })

  it('shows the empty-state when there are no runs', async () => {
    vi.spyOn(api.runs, 'list').mockResolvedValue({ runs: [], total: 0 })

    renderWithProviders(<RunsListPage />)

    expect(await screen.findByText('No playbook runs')).toBeInTheDocument()
  })

  it('expands a run row to reveal its timeline of action steps', async () => {
    vi.spyOn(api.runs, 'list').mockResolvedValue({
      runs: [
        makeRun({
          id: 'r-1',
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
          ],
        }),
      ],
      total: 1,
    })

    renderWithProviders(<RunsListPage />)

    await screen.findAllByText('Triage IP')
    // action_name is only rendered after the row is expanded
    expect(screen.queryByText('lookup_ip')).not.toBeInTheDocument()

    const rowSpan = screen
      .getAllByText('Triage IP')
      .find((el) => el.tagName.toLowerCase() === 'span')
    expect(rowSpan).toBeDefined()
    await userEvent.click(rowSpan as HTMLElement)
    expect(await screen.findByText('lookup_ip')).toBeInTheDocument()
    expect(screen.getByText('Action Steps')).toBeInTheDocument()
  })
})
