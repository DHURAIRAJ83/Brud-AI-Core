import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LanguageIntelligenceTab from './LanguageIntelligenceTab.jsx'

function baseProps(overrides = {}) {
  return {
    liSubTab: 'Overview',
    setLiSubTab: vi.fn(),
    liDiag: null,
    liSessionData: null,
    liSessionsList: [],
    liSelectedId: '',
    selectLiSession: vi.fn(),
    submitLiCreateSession: vi.fn((event) => event?.preventDefault?.()),
    liNewSourceId: '',
    setLiNewSourceId: vi.fn(),
    liBusy: false,
    liEventsList: [],
    runLiLanguageScan: vi.fn(),
    runLiUnicodeValidation: vi.fn(),
    runLiSpellAnalysis: vi.fn(),
    runLiGrammarAnalysis: vi.fn(),
    runLiOcrAnalysis: vi.fn(),
    runLiTanglishAnalysis: vi.fn(),
    runLiTranslationAnalysis: vi.fn(),
    runLiDatasetDraft: vi.fn(),
    runLiQualityScore: vi.fn(),
    runLiGenerateReport: vi.fn(),
    runLiAdminReview: vi.fn(),
    ...overrides,
  }
}

describe('LanguageIntelligenceTab', () => {
  it('renders all 11 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setLiSubTab = vi.fn()
    render(<LanguageIntelligenceTab {...baseProps({ setLiSubTab })} />)
    for (const label of ['Overview', 'Language Scan', 'Unicode & Character', 'Spell & Grammar', 'OCR', 'Tanglish', 'Translation', 'Dataset Draft', 'Quality & Report', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'OCR' }))
    expect(setLiSubTab).toHaveBeenCalledWith('OCR')
  })

  it('Overview: starts a real new language cycle', async () => {
    const user = userEvent.setup()
    const submitLiCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<LanguageIntelligenceTab {...baseProps({ liNewSourceId: 'src-1', submitLiCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start language cycle' }))
    expect(submitLiCreateSession).toHaveBeenCalled()
  })

  it('Language Scan: calls the real scan action', async () => {
    const user = userEvent.setup()
    const runLiLanguageScan = vi.fn()
    render(<LanguageIntelligenceTab {...baseProps({
      liSubTab: 'Language Scan',
      liSessionData: { dataset_source_public_id: 'src-12345678', stage: 'language_scan', status: 'active' },
      runLiLanguageScan,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Run language scan' }))
    expect(runLiLanguageScan).toHaveBeenCalled()
  })

  it('Quality & Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runLiAdminReview = vi.fn()
    render(<LanguageIntelligenceTab {...baseProps({
      liSubTab: 'Quality & Report',
      liSessionData: { dataset_source_public_id: 'src-12345678', stage: 'awaiting_admin_review', status: 'active', language_report: {} },
      runLiAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runLiAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<LanguageIntelligenceTab {...baseProps({ liSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
