import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MultimodalDatasetGeneratorTab from './MultimodalDatasetGeneratorTab.jsx'

function baseProps(overrides = {}) {
  return {
    mdSubTab: 'Overview',
    setMdSubTab: vi.fn(),
    mdDiag: null,
    mdSessionData: null,
    mdSessionsList: [],
    mdSelectedId: '',
    selectMdSession: vi.fn(),
    submitMdCreateSession: vi.fn((event) => event?.preventDefault?.()),
    mdNewDocumentId: '',
    setMdNewDocumentId: vi.fn(),
    mdNewVisionSessionId: '',
    setMdNewVisionSessionId: vi.fn(),
    mdNewLanguageSessionId: '',
    setMdNewLanguageSessionId: vi.fn(),
    mdNewVisionModelSessionId: '',
    setMdNewVisionModelSessionId: vi.fn(),
    mdBusy: false,
    mdEventsList: [],
    runMdCollectSources: vi.fn(),
    runMdMergeMetadata: vi.fn(),
    runMdCollectText: vi.fn(),
    runMdCollectImages: vi.fn(),
    runMdConversationBuilder: vi.fn(),
    runMdInstructionBuilder: vi.fn(),
    mdRecordsList: [],
    runMdDatasetDraft: vi.fn(),
    submitMdSplit: vi.fn((event) => event?.preventDefault?.()),
    mdSplitRecordIds: '',
    setMdSplitRecordIds: vi.fn(),
    submitMdMerge: vi.fn((event) => event?.preventDefault?.()),
    mdMergeSessionIds: '',
    setMdMergeSessionIds: vi.fn(),
    mdExportFormat: 'json',
    setMdExportFormat: vi.fn(),
    runMdExportDraft: vi.fn(),
    runMdDeleteDraft: vi.fn(),
    mdExportResult: null,
    runMdQualityAnalysis: vi.fn(),
    runMdDuplicateDetection: vi.fn(),
    runMdGenerateReport: vi.fn(),
    runMdAdminReview: vi.fn(),
    mdMemoryList: [],
    ...overrides,
  }
}

describe('MultimodalDatasetGeneratorTab', () => {
  it('renders all 12 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setMdSubTab = vi.fn()
    render(<MultimodalDatasetGeneratorTab {...baseProps({ setMdSubTab })} />)
    for (const label of ['Overview', 'Sources', 'Images', 'Text', 'Conversation', 'Instructions', 'QA', 'Dataset Draft', 'Quality', 'Reports', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Conversation' }))
    expect(setMdSubTab).toHaveBeenCalledWith('Conversation')
  })

  it('Overview: starts a real new dataset cycle', async () => {
    const user = userEvent.setup()
    const submitMdCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<MultimodalDatasetGeneratorTab {...baseProps({ mdNewDocumentId: 'doc-1', submitMdCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start dataset cycle' }))
    expect(submitMdCreateSession).toHaveBeenCalled()
  })

  it('Sources: calls the real collect sources action', async () => {
    const user = userEvent.setup()
    const runMdCollectSources = vi.fn()
    render(<MultimodalDatasetGeneratorTab {...baseProps({
      mdSubTab: 'Sources',
      mdSessionData: { document_source_public_id: 'doc-12345678', stage: 'collect_sources', status: 'active' },
      runMdCollectSources,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Collect sources' }))
    expect(runMdCollectSources).toHaveBeenCalled()
  })

  it('Reports: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runMdAdminReview = vi.fn()
    render(<MultimodalDatasetGeneratorTab {...baseProps({
      mdSubTab: 'Reports',
      mdSessionData: { document_source_public_id: 'doc-12345678', stage: 'awaiting_admin_review', status: 'active', dataset_report: {} },
      runMdAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runMdAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<MultimodalDatasetGeneratorTab {...baseProps({ mdSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
