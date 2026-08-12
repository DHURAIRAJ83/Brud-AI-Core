import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VisionModelCenterTab from './VisionModelCenterTab.jsx'

function baseProps(overrides = {}) {
  return {
    vmSubTab: 'Overview',
    setVmSubTab: vi.fn(),
    vmDiag: null,
    vmSessionData: null,
    vmSessionsList: [],
    vmSelectedId: '',
    selectVmSession: vi.fn(),
    submitVmCreateSession: vi.fn((event) => event?.preventDefault?.()),
    vmNewVisionSessionId: '',
    setVmNewVisionSessionId: vi.fn(),
    vmNewProviderKey: '',
    setVmNewProviderKey: vi.fn(),
    vmProvidersList: [],
    vmBusy: false,
    vmEventsList: [],
    toggleVmProviderStatus: vi.fn(),
    runVmImageLoad: vi.fn(),
    vmModelPath: '',
    setVmModelPath: vi.fn(),
    vmMmprojPath: '',
    setVmMmprojPath: vi.fn(),
    runVmProviderSelection: vi.fn(),
    runVmObjectDetection: vi.fn(),
    vmPredictionsList: [],
    submitVmReview: vi.fn((event) => event?.preventDefault?.()),
    vmReviewAction: 'approve',
    setVmReviewAction: vi.fn(),
    vmReviewPredictionId: '',
    setVmReviewPredictionId: vi.fn(),
    vmReviewLabel: '',
    setVmReviewLabel: vi.fn(),
    vmReviewImageId: '',
    setVmReviewImageId: vi.fn(),
    vmReviewBoxX: '',
    setVmReviewBoxX: vi.fn(),
    vmReviewBoxY: '',
    setVmReviewBoxY: vi.fn(),
    vmReviewBoxW: '',
    setVmReviewBoxW: vi.fn(),
    vmReviewBoxH: '',
    setVmReviewBoxH: vi.fn(),
    runVmFinishReview: vi.fn(),
    runVmSceneDetection: vi.fn(),
    runVmCaption: vi.fn(),
    runVmRelationshipDetection: vi.fn(),
    vmDatasetTextInput: '',
    setVmDatasetTextInput: vi.fn(),
    runVmOcrCrossValidation: vi.fn(),
    runVmKnowledgeGraph: vi.fn(),
    runVmCorrectionMemory: vi.fn(),
    vmCorrectionsList: [],
    vmLearningMemoryList: [],
    runVmQualityScore: vi.fn(),
    runVmDatasetDraft: vi.fn(),
    runVmGenerateReport: vi.fn(),
    runVmAdminReview: vi.fn(),
    ...overrides,
  }
}

describe('VisionModelCenterTab', () => {
  it('renders all 11 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setVmSubTab = vi.fn()
    render(<VisionModelCenterTab {...baseProps({ setVmSubTab })} />)
    for (const label of ['Overview', 'Providers', 'Detection', 'Caption', 'Scene', 'Relationships', 'Corrections', 'Learning Memory', 'Reports', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Detection' }))
    expect(setVmSubTab).toHaveBeenCalledWith('Detection')
  })

  it('Overview: starts a real new vision model cycle', async () => {
    const user = userEvent.setup()
    const submitVmCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<VisionModelCenterTab {...baseProps({ vmNewVisionSessionId: 'vis-1', submitVmCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start vision model cycle' }))
    expect(submitVmCreateSession).toHaveBeenCalled()
  })

  it('Providers: real activate/deactivate toggle calls the handler', async () => {
    const user = userEvent.setup()
    const toggleVmProviderStatus = vi.fn()
    render(<VisionModelCenterTab {...baseProps({
      vmSubTab: 'Providers',
      vmProvidersList: [{ provider_key: 'llava', display_name: 'LLaVA', backend_type: 'gguf', hardware_target: 'cpu', status: 'active', description: 'desc' }],
      toggleVmProviderStatus,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Deactivate' }))
    expect(toggleVmProviderStatus).toHaveBeenCalledWith('llava', 'active')
  })

  it('Detection: real admin review form submit calls the handler', async () => {
    const user = userEvent.setup()
    const submitVmReview = vi.fn((event) => event?.preventDefault?.())
    render(<VisionModelCenterTab {...baseProps({
      vmSubTab: 'Detection',
      vmSessionData: { vision_session_public_id: 'vis-12345678', provider_key: 'llava', stage: 'admin_review', status: 'active' },
      submitVmReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Apply review' }))
    expect(submitVmReview).toHaveBeenCalled()
  })

  it('Reports: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runVmAdminReview = vi.fn()
    render(<VisionModelCenterTab {...baseProps({
      vmSubTab: 'Reports',
      vmSessionData: { vision_session_public_id: 'vis-12345678', provider_key: 'llava', stage: 'awaiting_admin_review', status: 'active', vision_report: {} },
      runVmAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runVmAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<VisionModelCenterTab {...baseProps({ vmSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
