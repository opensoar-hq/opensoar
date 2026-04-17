import { describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider, useToast } from './Toast'

function Trigger({ onReady }: { onReady: (toast: ReturnType<typeof useToast>) => void }) {
  const toast = useToast()
  onReady(toast)
  return null
}

function renderWithProvider() {
  let toastApi: ReturnType<typeof useToast> | null = null
  render(
    <ToastProvider>
      <Trigger onReady={(t) => { toastApi = t }} />
    </ToastProvider>,
  )
  if (!toastApi) throw new Error('toast api not ready')
  return toastApi as ReturnType<typeof useToast>
}

describe('Toast', () => {
  it('renders a toast when error() is called', () => {
    const toast = renderWithProvider()
    act(() => { toast.error('Something broke', 'Details here') })
    expect(screen.getByText('Something broke')).toBeInTheDocument()
    expect(screen.getByText('Details here')).toBeInTheDocument()
  })

  it('can be dismissed via the close button', async () => {
    const user = userEvent.setup()
    const toast = renderWithProvider()
    act(() => { toast.success('Saved') })
    expect(screen.getByText('Saved')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(screen.queryByText('Saved')).not.toBeInTheDocument()
  })

  it('renders an action button (e.g. Retry) and fires callback', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    const toast = renderWithProvider()
    act(() => {
      toast.error('Failed to load', 'Network down', {
        action: { label: 'Retry', onClick: onRetry },
      })
    })

    const retryBtn = await screen.findByRole('button', { name: 'Retry' })
    await user.click(retryBtn)
    expect(onRetry).toHaveBeenCalledTimes(1)
    // action click also dismisses the toast
    expect(screen.queryByText('Failed to load')).not.toBeInTheDocument()
  })

  it('auto-dismisses non-action toasts after their duration', () => {
    vi.useFakeTimers()
    try {
      const toast = renderWithProvider()
      act(() => { toast.info('Heads up') })
      expect(screen.getByText('Heads up')).toBeInTheDocument()

      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByText('Heads up')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('keeps action toasts on screen longer (no auto-dismiss within normal window)', () => {
    vi.useFakeTimers()
    try {
      const toast = renderWithProvider()
      act(() => {
        toast.error('Persistent', undefined, { action: { label: 'Retry', onClick: () => {} } })
      })
      expect(screen.getByText('Persistent')).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      // still present because action toasts stay longer
      expect(screen.getByText('Persistent')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
