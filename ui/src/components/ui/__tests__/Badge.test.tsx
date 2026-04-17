import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge, SeverityBadge, StatusBadge, DeterminationBadge } from '@/components/ui/Badge'

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge>new</Badge>)
    expect(screen.getByText('new')).toBeInTheDocument()
  })

  it('applies a custom color via inline style', () => {
    render(<Badge color="rgb(255, 0, 0)">high</Badge>)
    const el = screen.getByText('high')
    expect(el).toHaveStyle({ color: 'rgb(255, 0, 0)' })
  })
})

describe('SeverityBadge', () => {
  it('renders the severity value as the label', () => {
    render(<SeverityBadge severity="critical" />)
    expect(screen.getByText('critical')).toBeInTheDocument()
  })
})

describe('StatusBadge', () => {
  it('humanises the status by replacing underscores with spaces', () => {
    render(<StatusBadge status="in_progress" />)
    expect(screen.getByText('in progress')).toBeInTheDocument()
  })

  it('keeps the status text intact when no underscore is present', () => {
    render(<StatusBadge status="new" />)
    expect(screen.getByText('new')).toBeInTheDocument()
  })
})

describe('DeterminationBadge', () => {
  it('renders the determination label', () => {
    render(<DeterminationBadge determination="malicious" />)
    expect(screen.getByText('malicious')).toBeInTheDocument()
  })
})
