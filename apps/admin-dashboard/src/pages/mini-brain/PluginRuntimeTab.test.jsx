import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PluginRuntimeTab from './PluginRuntimeTab.jsx'

function baseProps(overrides = {}) {
  return {
    prSubTab: 'Overview',
    setPrSubTab: vi.fn(),
    prDiag: null,
    prStats: null,
    submitPrExecute: vi.fn((event) => event?.preventDefault?.()),
    prExecForm: { plugin_public_id: '', scope_key: '', arguments: '', execution_token: '', timeout_seconds: '' },
    setPrExecForm: vi.fn(),
    prBusy: false,
    prExecResult: null,
    prExecutionsList: [],
    prSelectedExecutionId: '',
    selectPrExecution: vi.fn(),
    runPrCancel: vi.fn(),
    prExecutionData: null,
    prLogs: null,
    runPrGenerateReport: vi.fn(),
    runPrArchive: vi.fn(),
    prReportResult: null,
    submitPrPublicExecute: vi.fn((event) => event?.preventDefault?.()),
    prPublicForm: { plugin_public_id: '', scope_key: '', arguments: '', raw_user_identity: '', execution_token: '' },
    setPrPublicForm: vi.fn(),
    prPublicResult: null,
    runPrReportEvent: vi.fn(),
    prMemoryList: [],
    ...overrides,
  }
}

describe('PluginRuntimeTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setPrSubTab = vi.fn()
    render(<PluginRuntimeTab {...baseProps({ setPrSubTab })} />)
    for (const label of ['Overview', 'Execute', 'Active Executions', 'Results', 'Filesystem', 'Network', 'Permissions', 'Consents', 'Public Chat', 'Admin Assistant', 'Audit', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Results' }))
    expect(setPrSubTab).toHaveBeenCalledWith('Results')
  })

  it('Execute: submits a real execution form', async () => {
    const user = userEvent.setup()
    const submitPrExecute = vi.fn((event) => event?.preventDefault?.())
    render(<PluginRuntimeTab {...baseProps({
      prSubTab: 'Execute',
      prExecForm: { plugin_public_id: 'plugin-1', scope_key: 'network.http.allowed_domains', arguments: '{}', execution_token: '{"token":"x"}', timeout_seconds: '30' },
      submitPrExecute,
    })} />)
    const form = screen.getByPlaceholderText('network.http.allowed_domains').closest('form')
    await user.click(within(form).getByRole('button', { name: 'Execute' }))
    expect(submitPrExecute).toHaveBeenCalled()
  })

  it('Active Executions: selects a real execution', async () => {
    const user = userEvent.setup()
    const selectPrExecution = vi.fn()
    render(<PluginRuntimeTab {...baseProps({
      prSubTab: 'Active Executions',
      prExecutionsList: [{ public_id: 'exec-1', plugin_public_id: 'plugin-12345678', execution_mode: 'admin', status: 'completed', scope_key: 'network.http.allowed_domains' }],
      selectPrExecution,
    })} />)
    await user.click(screen.getByRole('button', { name: /plugin-1/ }))
    expect(selectPrExecution).toHaveBeenCalledWith('exec-1')
  })

  it('Results: real generate report button calls the handler', async () => {
    const user = userEvent.setup()
    const runPrGenerateReport = vi.fn()
    render(<PluginRuntimeTab {...baseProps({
      prSubTab: 'Results',
      prExecutionData: { status: 'completed', duration_ms: 42 },
      runPrGenerateReport,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(runPrGenerateReport).toHaveBeenCalled()
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<PluginRuntimeTab {...baseProps({ prSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
