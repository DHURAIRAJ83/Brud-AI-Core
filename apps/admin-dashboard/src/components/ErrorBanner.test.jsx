import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ErrorBanner from './ErrorBanner.jsx'

describe('ErrorBanner', () => {
  it('renders the default title and the real error message', () => {
    render(<ErrorBanner message="Network error." />)
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.getByRole('alert')).toHaveTextContent('Network error.')
  })

  it('renders a custom title when given one', () => {
    render(<ErrorBanner title="Unable to load pilot metrics" message="Network error." />)
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to load pilot metrics')
  })

  it('shows a Retry button that calls onRetry when clicked', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    render(<ErrorBanner message="Network error." onRetry={onRetry} />)
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('omits the Retry button when no onRetry is given', () => {
    render(<ErrorBanner message="Network error." />)
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })
})
