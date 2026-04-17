import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExecutionPlan } from '@/components/ui/ExecutionPlan'

const baseStep = {
  started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:00:01Z',
  duration_ms: 1000,
  input_data: null,
  output_data: null,
  error: null,
  attempt: 1,
}

describe('ExecutionPlan', () => {
  it('renders the playbook name and step counts', () => {
    render(
      <ExecutionPlan
        run={{
          id: 'r-1',
          playbook_name: 'Triage IP',
          status: 'completed',
          started_at: '2026-01-01T00:00:00Z',
          finished_at: '2026-01-01T00:00:03Z',
          error: null,
          result: null,
          steps: [
            { id: 's1', action_name: 'lookup_ip', status: 'completed', ...baseStep },
            { id: 's2', action_name: 'enrich_ip', status: 'completed', ...baseStep },
            { id: 's3', action_name: 'post_slack', status: 'failed', ...baseStep, error: 'boom' },
          ],
        }}
      />,
    )

    expect(screen.getByText('Triage IP')).toBeInTheDocument()
    expect(screen.getByText(/2\/3 steps/)).toBeInTheDocument()
    expect(screen.getByText(/1 failed/)).toBeInTheDocument()
    expect(screen.getByText('lookup_ip')).toBeInTheDocument()
    expect(screen.getByText('enrich_ip')).toBeInTheDocument()
    expect(screen.getByText('post_slack')).toBeInTheDocument()
  })

  it('auto-expands failed steps to reveal the error', () => {
    render(
      <ExecutionPlan
        run={{
          id: 'r-2',
          playbook_name: 'Failing run',
          status: 'failed',
          started_at: null,
          finished_at: null,
          error: null,
          result: null,
          steps: [
            {
              id: 's1',
              action_name: 'broken_action',
              status: 'failed',
              ...baseStep,
              error: 'connection refused',
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('connection refused')).toBeInTheDocument()
  })

  it('renders a run-level error banner when the run failed without steps', () => {
    render(
      <ExecutionPlan
        run={{
          id: 'r-3',
          playbook_name: 'Broken',
          status: 'failed',
          started_at: null,
          finished_at: null,
          error: 'Playbook failed to start',
          result: null,
          steps: [],
        }}
      />,
    )

    expect(screen.getByText(/Run Error/i)).toBeInTheDocument()
    expect(screen.getByText('Playbook failed to start')).toBeInTheDocument()
  })

  it('toggles step details when clicked', async () => {
    render(
      <ExecutionPlan
        run={{
          id: 'r-4',
          playbook_name: 'Toggle',
          status: 'completed',
          started_at: '2026-01-01T00:00:00Z',
          finished_at: '2026-01-01T00:00:01Z',
          error: null,
          result: null,
          steps: [
            {
              id: 's1',
              action_name: 'enrich',
              status: 'completed',
              ...baseStep,
              input_data: { ip: '1.2.3.4' },
              output_data: { verdict: 'clean' },
            },
          ],
        }}
      />,
    )

    // Output section isn't visible until the step is expanded
    expect(screen.queryByText('Output')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('enrich'))
    expect(screen.getByText('Output')).toBeInTheDocument()
    expect(screen.getByText('Input')).toBeInTheDocument()
  })
})
