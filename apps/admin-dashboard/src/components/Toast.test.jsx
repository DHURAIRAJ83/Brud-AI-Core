import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider, useToast } from './Toast.jsx'

function Probe() {
  const toast = useToast()
  return (
    <div>
      <button onClick={() => toast.success('Saved successfully')}>Fire success</button>
      <button onClick={() => toast.error('Something failed', { duration: 0 })}>Fire error</button>
    </div>
  )
}

describe('Toast / ToastProvider', () => {
  it('renders nothing when there are no toasts', () => {
    render(<ToastProvider><Probe /></ToastProvider>)
    expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument()
  })

  it('shows a success toast with the right variant class', async () => {
    const user = userEvent.setup()
    render(<ToastProvider><Probe /></ToastProvider>)
    await user.click(screen.getByRole('button', { name: 'Fire success' }))
    const toast = screen.getByText('Saved successfully').closest('.toast')
    expect(toast.className).toContain('toast-success')
  })

  it('shows an error toast with the right variant class', async () => {
    const user = userEvent.setup()
    render(<ToastProvider><Probe /></ToastProvider>)
    await user.click(screen.getByRole('button', { name: 'Fire error' }))
    const toast = screen.getByText('Something failed').closest('.toast')
    expect(toast.className).toContain('toast-error')
  })

  it('dismisses a toast when its close button is clicked', async () => {
    const user = userEvent.setup()
    render(<ToastProvider><Probe /></ToastProvider>)
    await user.click(screen.getByRole('button', { name: 'Fire error' }))
    expect(screen.getByText('Something failed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Dismiss notification' }))
    expect(screen.queryByText('Something failed')).not.toBeInTheDocument()
  })

  it('auto-dismisses after its duration elapses', () => {
    vi.useFakeTimers()
    try {
      render(<ToastProvider><Probe /></ToastProvider>)
      act(() => { fireEvent.click(screen.getByRole('button', { name: 'Fire success' })) })
      expect(screen.getByText('Saved successfully')).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByText('Saved successfully')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('useToast throws when used outside a ToastProvider', () => {
    function Bare() {
      useToast()
      return null
    }
    expect(() => render(<Bare />)).toThrow('useToast must be used within a ToastProvider')
  })
})
