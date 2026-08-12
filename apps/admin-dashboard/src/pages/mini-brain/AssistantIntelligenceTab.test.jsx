import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AssistantIntelligenceTab from './AssistantIntelligenceTab.jsx'

vi.mock('../../services/api.js', () => ({
  lrChat: vi.fn().mockResolvedValue({ reply: { sanitized_text: 'ok' } }),
  lrDeleteSession: vi.fn().mockResolvedValue({}),
  lrMessages: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  lrSessions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  miniBrainDefaultRetrievalProfile: vi.fn().mockResolvedValue({}),
  sendMiniBrainGroundedMessage: vi.fn().mockResolvedValue({}),
}))

function baseProps(overrides = {}) {
  return {
    admin: null,
    toast: null,
    lrDiag: null,
    lrSubTab: 'Chat',
    setLrSubTab: vi.fn(),
    submitLrExplainPage: vi.fn((event) => event?.preventDefault?.()),
    lrExplainPageForm: { page_id: '', nav_key: '' },
    setLrExplainPageForm: vi.fn(),
    lrBusy: false,
    submitLrSummarizeReport: vi.fn((event) => event?.preventDefault?.()),
    lrReportForm: '',
    setLrReportForm: vi.fn(),
    submitLrSummarizeRegression: vi.fn((event) => event?.preventDefault?.()),
    lrRegressionForm: '',
    setLrRegressionForm: vi.fn(),
    submitLrExplainError: vi.fn((event) => event?.preventDefault?.()),
    lrErrorForm: '',
    setLrErrorForm: vi.fn(),
    submitLrNextActions: vi.fn((event) => event?.preventDefault?.()),
    lrStatusSnapshotForm: '',
    setLrStatusSnapshotForm: vi.fn(),
    lrNextActionsResult: null,
    lrLocalModelConfig: { model_path: '', context_length: '', max_tokens: '', temperature: '', threads: '' },
    setLrLocalModelConfig: vi.fn(),
    saveLrLocalModelConfig: vi.fn(),
    ...overrides,
  }
}

describe('AssistantIntelligenceTab', () => {
  it('renders all 8 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setLrSubTab = vi.fn()
    render(<AssistantIntelligenceTab {...baseProps({ setLrSubTab })} />)
    for (const label of ['Chat', 'Explain Page', 'Summarize Report', 'Summarize Regression', 'Explain Error', 'Next Actions', 'Local Model Config', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Explain Page' }))
    expect(setLrSubTab).toHaveBeenCalledWith('Explain Page')
  })

  it('Chat sub-tab renders the real shared ChatPanel', async () => {
    render(<AssistantIntelligenceTab {...baseProps()} />)
    expect(await screen.findByLabelText('Message')).toBeInTheDocument()
  })

  it('Explain Page: submits the real form', async () => {
    const user = userEvent.setup()
    const submitLrExplainPage = vi.fn((event) => event?.preventDefault?.())
    render(<AssistantIntelligenceTab {...baseProps({ lrSubTab: 'Explain Page', submitLrExplainPage })} />)
    await user.click(screen.getByRole('button', { name: 'Explain this page' }))
    expect(submitLrExplainPage).toHaveBeenCalled()
  })

  it('Local Model Config: real save button calls the handler', async () => {
    const user = userEvent.setup()
    const saveLrLocalModelConfig = vi.fn()
    render(<AssistantIntelligenceTab {...baseProps({ lrSubTab: 'Local Model Config', saveLrLocalModelConfig })} />)
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(saveLrLocalModelConfig).toHaveBeenCalled()
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<AssistantIntelligenceTab {...baseProps({ lrSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
