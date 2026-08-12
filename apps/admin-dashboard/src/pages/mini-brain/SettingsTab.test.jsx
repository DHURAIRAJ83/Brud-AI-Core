import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsTab from './SettingsTab.jsx'

describe('SettingsTab', () => {
  it('renders nothing until settings has loaded', () => {
    const { container } = render(<SettingsTab settings={null} logLevel="info" setLogLevel={vi.fn()} saveSettings={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the real runtime backend and current log level once loaded', () => {
    render(<SettingsTab settings={{ config: { runtime_backend: 'local' } }} logLevel="warning" setLogLevel={vi.fn()} saveSettings={vi.fn()} />)
    expect(screen.getByText('local')).toBeInTheDocument()
    expect(screen.getByLabelText('Log level')).toHaveValue('warning')
  })

  it('calls setLogLevel when changed, and saveSettings on submit', async () => {
    const user = userEvent.setup()
    const setLogLevel = vi.fn()
    const saveSettings = vi.fn((event) => event.preventDefault())
    render(<SettingsTab settings={{ config: { runtime_backend: 'local' } }} logLevel="info" setLogLevel={setLogLevel} saveSettings={saveSettings} />)
    await user.selectOptions(screen.getByLabelText('Log level'), 'debug')
    expect(setLogLevel).toHaveBeenCalledWith('debug')
    await user.click(screen.getByRole('button', { name: 'Save configuration' }))
    expect(saveSettings).toHaveBeenCalled()
  })
})
