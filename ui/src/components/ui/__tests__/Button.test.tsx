import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '@/components/ui/Button'

describe('Button', () => {
  it('renders its children and handles clicks', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Save</Button>)
    const btn = screen.getByRole('button', { name: 'Save' })
    await userEvent.click(btn)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not fire onClick when disabled', async () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} disabled>
        Save
      </Button>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('applies the primary variant class', () => {
    render(<Button variant="primary">Go</Button>)
    const btn = screen.getByRole('button', { name: 'Go' })
    expect(btn.className).toMatch(/bg-accent/)
  })
})
