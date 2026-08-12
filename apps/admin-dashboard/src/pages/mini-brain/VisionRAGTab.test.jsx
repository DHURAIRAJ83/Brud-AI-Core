import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VisionRAGTab from './VisionRAGTab.jsx'

function baseProps(overrides = {}) {
  return {
    vrSubTab: 'Overview',
    setVrSubTab: vi.fn(),
    vrDiag: null,
    vrSessionData: null,
    vrSessionsList: [],
    vrSelectedId: '',
    selectVrSession: vi.fn(),
    submitVrCreateSession: vi.fn((event) => event?.preventDefault?.()),
    vrNewDatasetSessionId: '',
    setVrNewDatasetSessionId: vi.fn(),
    vrNewQuery: '',
    setVrNewQuery: vi.fn(),
    vrBusy: false,
    vrEventsList: [],
    runVrTextRetrieval: vi.fn(),
    runVrAnswer: vi.fn(),
    runVrEvidenceFusion: vi.fn(),
    vrEvidenceList: [],
    runVrImageRetrieval: vi.fn(),
    runVrOcrRetrieval: vi.fn(),
    runVrObjectRetrieval: vi.fn(),
    runVrKnowledgeGraphRetrieval: vi.fn(),
    runVrQuality: vi.fn(),
    runVrHallucinationCheck: vi.fn(),
    runVrGenerateReport: vi.fn(),
    submitVrCorrect: vi.fn((event) => event?.preventDefault?.()),
    vrCorrectAction: 'correct_answer',
    setVrCorrectAction: vi.fn(),
    vrCorrectAnswer: '',
    setVrCorrectAnswer: vi.fn(),
    vrCorrectEvidenceId: '',
    setVrCorrectEvidenceId: vi.fn(),
    vrCorrectSnippet: '',
    setVrCorrectSnippet: vi.fn(),
    vrAddEvidenceType: 'text',
    setVrAddEvidenceType: vi.fn(),
    runVrAdminReview: vi.fn(),
    vrMemoryList: [],
    ...overrides,
  }
}

describe('VisionRAGTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setVrSubTab = vi.fn()
    render(<VisionRAGTab {...baseProps({ setVrSubTab })} />)
    for (const label of ['Overview', 'Query', 'Results', 'Evidence', 'Images', 'OCR', 'Objects', 'Graph', 'Quality', 'Hallucinations', 'History', 'Reports', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Evidence' }))
    expect(setVrSubTab).toHaveBeenCalledWith('Evidence')
  })

  it('Overview: asks a real new query', async () => {
    const user = userEvent.setup()
    const submitVrCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<VisionRAGTab {...baseProps({ vrNewDatasetSessionId: 'ds-1', vrNewQuery: 'where?', submitVrCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    expect(submitVrCreateSession).toHaveBeenCalled()
  })

  it('Query: calls the real text retrieval action', async () => {
    const user = userEvent.setup()
    const runVrTextRetrieval = vi.fn()
    render(<VisionRAGTab {...baseProps({
      vrSubTab: 'Query',
      vrSessionData: { query: 'where is the river?', query_language: 'en', stage: 'query_session', status: 'active' },
      runVrTextRetrieval,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Run text retrieval' }))
    expect(runVrTextRetrieval).toHaveBeenCalled()
  })

  it('Reports: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runVrAdminReview = vi.fn()
    render(<VisionRAGTab {...baseProps({
      vrSubTab: 'Reports',
      vrSessionData: { query: 'q', stage: 'awaiting_admin_review', status: 'active', rag_report: {} },
      runVrAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runVrAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<VisionRAGTab {...baseProps({ vrSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
