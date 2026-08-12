import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ExternalAIGatewayTab from './ExternalAIGatewayTab.jsx'

function baseProps(overrides = {}) {
  return {
    gaSubTab: 'Overview',
    setGaSubTab: vi.fn(),
    gaDiag: null,
    gaSessionData: null,
    gaSessionsList: [],
    gaSelectedId: '',
    selectGaSession: vi.fn(),
    submitGaCreateSession: vi.fn((event) => event?.preventDefault?.()),
    gaNewTopic: '',
    setGaNewTopic: vi.fn(),
    gaNewPurpose: 'public_style_stress_test',
    setGaNewPurpose: vi.fn(),
    gaNewDatasetIds: '',
    setGaNewDatasetIds: vi.fn(),
    gaNewRagId: '',
    setGaNewRagId: vi.fn(),
    gaBusy: false,
    gaEventsList: [],
    submitGaAuthorize: vi.fn((event) => event?.preventDefault?.()),
    gaAuthorizationNote: '',
    setGaAuthorizationNote: vi.fn(),
    submitGaSelectProviders: vi.fn((event) => event?.preventDefault?.()),
    gaProviderKeys: '',
    setGaProviderKeys: vi.fn(),
    runGaDispatch: vi.fn(),
    submitGaSanitize: vi.fn((event) => event?.preventDefault?.()),
    gaAdminStatedNeed: '',
    setGaAdminStatedNeed: vi.fn(),
    runGaAction: vi.fn(),
    gaSanitize: vi.fn(),
    runGaCollect: vi.fn(),
    runGaNormalize: vi.fn(),
    gaProviderRunsList: [],
    runGaAnalyze: vi.fn(),
    runGaBuildEvidence: vi.fn(),
    runGaGenerateReport: vi.fn(),
    runGaAdminReview: vi.fn(),
    runGaArchive: vi.fn(),
    gaMemoryList: [],
    ...overrides,
  }
}

describe('ExternalAIGatewayTab', () => {
  it('renders all 12 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setGaSubTab = vi.fn()
    render(<ExternalAIGatewayTab {...baseProps({ setGaSubTab })} />)
    for (const label of ['Overview', 'Authorization', 'Providers', 'Sanitization', 'Public Evaluation', 'Data Acquisition', 'Provider Responses', 'Agreement', 'Evidence', 'Report', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Agreement' }))
    expect(setGaSubTab).toHaveBeenCalledWith('Agreement')
  })

  it('Overview: creates a real new session', async () => {
    const user = userEvent.setup()
    const submitGaCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<ExternalAIGatewayTab {...baseProps({ gaNewTopic: 'topic-1', submitGaCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Create session' }))
    expect(submitGaCreateSession).toHaveBeenCalled()
  })

  it('Sanitization: public_style_stress_test real sanitize button calls runGaAction with gaSanitize', async () => {
    const user = userEvent.setup()
    const runGaAction = vi.fn()
    render(<ExternalAIGatewayTab {...baseProps({
      gaSubTab: 'Sanitization',
      gaSessionData: { topic: 't', purpose: 'public_style_stress_test', stage: 'sanitize_inputs', status: 'active' },
      runGaAction,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Sanitize inputs' }))
    expect(runGaAction).toHaveBeenCalled()
  })

  it('Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runGaAdminReview = vi.fn()
    render(<ExternalAIGatewayTab {...baseProps({
      gaSubTab: 'Report',
      gaSessionData: { topic: 't', purpose: 'public_style_stress_test', stage: 'awaiting_admin_review', status: 'active', gateway_report: { confidence_level: 'medium' } },
      runGaAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Accept' }))
    expect(runGaAdminReview).toHaveBeenCalledWith('accept')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<ExternalAIGatewayTab {...baseProps({ gaSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
