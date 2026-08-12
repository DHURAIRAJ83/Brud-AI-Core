import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VisionIntelligenceTab from './VisionIntelligenceTab.jsx'

function baseProps(overrides = {}) {
  return {
    viSubTab: 'Overview',
    setViSubTab: vi.fn(),
    viDiag: null,
    viSessionData: null,
    viSessionsList: [],
    viSelectedId: '',
    selectViSession: vi.fn(),
    submitViCreateSession: vi.fn((event) => event?.preventDefault?.()),
    viNewDocumentSourceId: '',
    setViNewDocumentSourceId: vi.fn(),
    viNewDatasetSourceId: '',
    setViNewDatasetSourceId: vi.fn(),
    viBusy: false,
    viEventsList: [],
    runViImageExtraction: vi.fn(),
    viImagesList: [],
    runViImageQuality: vi.fn(),
    runViVisionUnderstanding: vi.fn(),
    viObjectsList: [],
    viDatasetTextInput: '',
    setViDatasetTextInput: vi.fn(),
    runViOcrCrossValidation: vi.fn(),
    viAdminCaptionInput: '',
    setViAdminCaptionInput: vi.fn(),
    runViCaption: vi.fn(),
    runViBoundingBoxPlan: vi.fn(),
    submitViAnnotate: vi.fn((event) => event?.preventDefault?.()),
    viAnnotateAction: 'rename',
    setViAnnotateAction: vi.fn(),
    viAnnotateObjectId: '',
    setViAnnotateObjectId: vi.fn(),
    viAnnotateLabel: '',
    setViAnnotateLabel: vi.fn(),
    viAnnotateImageId: '',
    setViAnnotateImageId: vi.fn(),
    viAnnotateCaption: '',
    setViAnnotateCaption: vi.fn(),
    viAnnotateBoxX: '',
    setViAnnotateBoxX: vi.fn(),
    viAnnotateBoxY: '',
    setViAnnotateBoxY: vi.fn(),
    viAnnotateBoxW: '',
    setViAnnotateBoxW: vi.fn(),
    viAnnotateBoxH: '',
    setViAnnotateBoxH: vi.fn(),
    runViFinishAnnotation: vi.fn(),
    runViKnowledgeGraph: vi.fn(),
    runViQaGeneration: vi.fn(),
    runViDatasetDraft: vi.fn(),
    runViQualityScore: vi.fn(),
    runViGenerateReport: vi.fn(),
    runViAdminReview: vi.fn(),
    ...overrides,
  }
}

describe('VisionIntelligenceTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setViSubTab = vi.fn()
    render(<VisionIntelligenceTab {...baseProps({ setViSubTab })} />)
    for (const label of ['Overview', 'Image Extraction', 'Quality', 'Objects', 'OCR Compare', 'Caption', 'Annotation', 'Knowledge Graph', 'QA', 'Vision Draft', 'Report', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Objects' }))
    expect(setViSubTab).toHaveBeenCalledWith('Objects')
  })

  it('Overview: starts a real new vision cycle', async () => {
    const user = userEvent.setup()
    const submitViCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<VisionIntelligenceTab {...baseProps({ viNewDocumentSourceId: 'doc-1', submitViCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start vision cycle' }))
    expect(submitViCreateSession).toHaveBeenCalled()
  })

  it('Image Extraction: calls the real extraction action', async () => {
    const user = userEvent.setup()
    const runViImageExtraction = vi.fn()
    render(<VisionIntelligenceTab {...baseProps({
      viSubTab: 'Image Extraction',
      viSessionData: { document_source_public_id: 'doc-12345678', stage: 'image_extraction', status: 'active' },
      runViImageExtraction,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Run image extraction' }))
    expect(runViImageExtraction).toHaveBeenCalled()
  })

  it('Annotation: real annotate form submit calls the handler', async () => {
    const user = userEvent.setup()
    const submitViAnnotate = vi.fn((event) => event?.preventDefault?.())
    render(<VisionIntelligenceTab {...baseProps({
      viSubTab: 'Annotation',
      viSessionData: { document_source_public_id: 'doc-12345678', stage: 'admin_annotation', status: 'active' },
      submitViAnnotate,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Apply annotation' }))
    expect(submitViAnnotate).toHaveBeenCalled()
  })

  it('Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runViAdminReview = vi.fn()
    render(<VisionIntelligenceTab {...baseProps({
      viSubTab: 'Report',
      viSessionData: { document_source_public_id: 'doc-12345678', stage: 'awaiting_admin_review', status: 'active', vision_report: {} },
      runViAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runViAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<VisionIntelligenceTab {...baseProps({ viSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
