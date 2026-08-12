import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import DiagnosticsTab from './DiagnosticsTab.jsx'

describe('DiagnosticsTab', () => {
  it('renders nothing until diagnostics has loaded', () => {
    const { container } = render(<DiagnosticsTab diagnostics={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows real diagnostics fields with a good tone when there are no config issues', () => {
    render(<DiagnosticsTab diagnostics={{ config_issues: [], event_count: 3, runtime_backend: 'local', model_integrated: false }} />)
    expect(screen.getByText('Config issues').closest('article')).toHaveTextContent('0')
    expect(screen.getByText('Event count').closest('article')).toHaveTextContent('3')
    expect(screen.getByText('Runtime backend').closest('article')).toHaveTextContent('local')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the real config issues list when present', () => {
    render(<DiagnosticsTab diagnostics={{ config_issues: ['missing model path'], event_count: 0, runtime_backend: 'local', model_integrated: false }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('missing model path')
  })
})
