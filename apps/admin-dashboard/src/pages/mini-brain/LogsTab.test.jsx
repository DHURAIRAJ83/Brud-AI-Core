import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import LogsTab from './LogsTab.jsx'

describe('LogsTab', () => {
  it('shows the real event total and no items when empty', () => {
    render(<LogsTab logs={{ total: 0, items: [] }} />)
    expect(screen.getByText('0 event(s) recorded, most recent first.')).toBeInTheDocument()
  })

  it('renders each real log item', () => {
    render(<LogsTab logs={{
      total: 1,
      items: [{ public_id: 'log-1', event_type: 'enable', level: 'info', message: 'Enabled.', created_at: '2026-01-01T00:00:00Z' }],
    }} />)
    expect(screen.getByText('enable')).toBeInTheDocument()
    expect(screen.getByText(/Enabled\./)).toBeInTheDocument()
  })
})
