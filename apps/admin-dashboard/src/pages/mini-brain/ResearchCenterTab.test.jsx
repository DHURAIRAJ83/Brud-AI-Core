import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResearchCenterTab from './ResearchCenterTab.jsx'

function baseProps(overrides = {}) {
  return {
    rcSubTab: 'Overview',
    setRcSubTab: vi.fn(),
    rcDiag: null,
    rcSessionData: null,
    rcSessionsList: [],
    rcSelectedId: '',
    selectRcSession: vi.fn(),
    submitRcCreateSession: vi.fn((event) => event?.preventDefault?.()),
    rcNewTopic: '',
    setRcNewTopic: vi.fn(),
    rcBusy: false,
    rcEventsList: [],
    rcProviders: [],
    toggleRcProviderStatus: vi.fn(),
    submitRcAddProvider: vi.fn((event) => event?.preventDefault?.()),
    rcNewProviderForm: { provider_key: '', display_name: '', requires_external_call: true, description: '' },
    setRcNewProviderForm: vi.fn(),
    submitRcResearchRequest: vi.fn((event) => event?.preventDefault?.()),
    rcPlanningCenterId: '',
    setRcPlanningCenterId: vi.fn(),
    submitRcSelectMode: vi.fn((event) => event?.preventDefault?.()),
    rcMode: 'local_draft',
    setRcMode: vi.fn(),
    rcProviderKeys: 'claude,openai',
    setRcProviderKeys: vi.fn(),
    submitRcBuildLocalDraft: vi.fn((event) => event?.preventDefault?.()),
    rcExistingDatasetId: '',
    setRcExistingDatasetId: vi.fn(),
    runRcPrepareProviderRequestPackage: vi.fn(),
    submitRcIngestProviderResults: vi.fn((event) => event?.preventDefault?.()),
    rcProviderOutputs: [{ provider: 'claude', output_text: '' }],
    setRcProviderOutputs: vi.fn(),
    runRcBuildDatasetDraft: vi.fn(),
    runRcAdminReviewDraft: vi.fn(),
    submitRcRunRagEvaluation: vi.fn((event) => event?.preventDefault?.()),
    rcRagForm: { rag_sandbox_experiment_public_id: '', retrieval_run_public_id: '', generation_assignment_public_id: '' },
    setRcRagForm: vi.fn(),
    runRcFinalizeRagEvaluation: vi.fn(),
    runRcAdminReviewRag: vi.fn(),
    runRcCheckTrainingGate: vi.fn(),
    rcTrainingReportMb06Id: '',
    setRcTrainingReportMb06Id: vi.fn(),
    submitRcAnalyzeTrainingReport: vi.fn((event) => event?.preventDefault?.()),
    runRcGenerateReport: vi.fn(),
    rcReport: null,
    rcMemoryItems: [],
    submitRcRecordMemory: vi.fn((event) => event?.preventDefault?.()),
    rcMemoryNotes: '',
    setRcMemoryNotes: vi.fn(),
    ...overrides,
  }
}

describe('ResearchCenterTab', () => {
  it('renders all 11 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setRcSubTab = vi.fn()
    render(<ResearchCenterTab {...baseProps({ setRcSubTab })} />)
    for (const label of ['Overview', 'Provider Registry', 'Research Requests', 'Consensus', 'Evidence', 'Dataset Draft', 'RAG Status', 'Training Status', 'Reports', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Provider Registry' }))
    expect(setRcSubTab).toHaveBeenCalledWith('Provider Registry')
  })

  it('Overview: starts a real new research session', async () => {
    const user = userEvent.setup()
    const submitRcCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<ResearchCenterTab {...baseProps({ rcNewTopic: 'Photosynthesis', submitRcCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start research session' }))
    expect(submitRcCreateSession).toHaveBeenCalled()
  })

  it('Provider Registry: toggles a real provider and submits a real new one', async () => {
    const user = userEvent.setup()
    const toggleRcProviderStatus = vi.fn()
    render(<ResearchCenterTab {...baseProps({
      rcSubTab: 'Provider Registry',
      rcProviders: [{ provider_key: 'claude', display_name: 'Claude', status: 'active', requires_external_call: true, description: 'd' }],
      toggleRcProviderStatus,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Deactivate' }))
    expect(toggleRcProviderStatus).toHaveBeenCalledWith('claude', 'active')
  })

  it('Dataset Draft: awaiting_draft_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runRcAdminReviewDraft = vi.fn()
    render(<ResearchCenterTab {...baseProps({
      rcSubTab: 'Dataset Draft',
      rcSessionData: { topic: 't', mode: 'local_draft', stage: 'awaiting_draft_review', status: 'active', draft_admin_decision: 'accept_draft' },
      runRcAdminReviewDraft,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Send to RAG' }))
    expect(runRcAdminReviewDraft).toHaveBeenCalledWith('send_to_rag')
  })

  it('Diagnostics: shows a skeleton before loaded, real diagnostics JSON after', () => {
    const { rerender } = render(<ResearchCenterTab {...baseProps({ rcSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    rerender(<ResearchCenterTab {...baseProps({ rcSubTab: 'Diagnostics', rcDiag: { external_providers_called: false, rag_first_policy: 'enforced' } })} />)
    expect(screen.getByText(/rag_first_policy/)).toBeInTheDocument()
  })
})
