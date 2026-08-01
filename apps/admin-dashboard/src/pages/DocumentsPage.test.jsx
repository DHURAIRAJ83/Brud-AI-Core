import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DocumentsPage from './DocumentsPage.jsx'

vi.mock('../services/api.js', () => ({
  analyzeDocument: vi.fn(), applyDocumentPageCleanup: vi.fn(), approveDocumentPage: vi.fn(),
  detectDocumentRepeatedElements: vi.fn(), documentCandidateAction: vi.fn(), documentCandidates: vi.fn(),
  documentCapabilities: vi.fn(), documentDetail: vi.fn(), documentJobEvents: vi.fn(), documentJobs: vi.fn(),
  documentPage: vi.fn(), documentPageCleanupSuggestions: vi.fn(), documentPageExtractions: vi.fn(),
  documentPageImageUrl: vi.fn(), documentPageReviewEvents: vi.fn(), documentPageRevisions: vi.fn(),
  documentPages: vi.fn(), documentRepeatedElements: vi.fn(), documentReviewSummary: vi.fn(),
  documentWorkspace: vi.fn(), documents: vi.fn(), downloadDocumentReport: vi.fn(),
  editDocumentCandidate: vi.fn(), editDocumentPage: vi.fn(), excludeDocumentPage: vi.fn(),
  importDocumentCandidates: vi.fn(), linkDocumentSource: vi.fn(), processDocument: vi.fn(),
  rejectDocumentPage: vi.fn(), reopenDocumentPage: vi.fn(), reprocessDocumentPage: vi.fn(),
  requestDocumentPageCorrection: vi.fn(), requestDocumentPageExtractionRerun: vi.fn(),
  requestDocumentPageOcrRerun: vi.fn(), restoreDocumentPageRevision: vi.fn(),
  reviewDocumentRepeatedElement: vi.fn(), segmentDocument: vi.fn(), sendDocumentToSegmentation: vi.fn(),
  uploadDocument: vi.fn(),
  detectDocumentTamilQuality: vi.fn(), documentTamilQualityIssues: vi.fn(), documentTamilQualitySummary: vi.fn(),
  reviewDocumentTamilQualityIssue: vi.fn(), generateDocumentSftCandidates: vi.fn(), documentSftCandidates: vi.fn(),
  documentSftCandidateSummary: vi.fn(), reviewDocumentSftCandidate: vi.fn(), bulkApproveDocumentSftCandidates: vi.fn(),
  exportDocumentSftCandidates: vi.fn(),
  scanDocumentSecurityFindings: vi.fn(), documentSecurityFindings: vi.fn(), documentPiiFindings: vi.fn(),
  reviewDocumentSecurityFinding: vi.fn(), scanDocumentContentClassifications: vi.fn(),
  documentContentClassifications: vi.fn(), tamilCorrectionRules: vi.fn(), createTamilCorrectionRule: vi.fn(),
  reviewTamilCorrectionRule: vi.fn(),
}))

const api = await import('../services/api.js')

const CAPABILITIES = { pdf_extraction: true, ocr_available: true, ocr_languages: ['eng', 'tam'], max_file_bytes: 26214400, max_pages: 300 }

const DOCUMENT = {
  public_id: 'doc-1', original_filename: 'sample.pdf', file_size_bytes: 1024, page_count: 2,
  status: 'review_ready', extraction_strategy: 'auto', checksum_prefix: 'abc123', detected_language: 'ta',
}

const PAGES = [
  { public_id: 'page-1', page_number: 1, extraction_method: 'embedded', extraction_status: 'success', text_length: 40, warnings: [] },
  { public_id: 'page-2', page_number: 2, extraction_method: 'embedded', extraction_status: 'success', text_length: 30, warnings: [] },
]

const WORKSPACE = {
  source_status: 'unlinked', source: null, rights_warnings: [],
  review_status_counts: { pending: 2, needs_correction: 0, corrected: 0, approved: 0, rejected: 0, excluded: 0 },
  low_confidence_page_count: 0, pages_with_warnings_count: 0, readiness: 'not_ready',
}

const PAGE_DETAIL = {
  public_id: 'page-1', page_number: 1, review_status: 'pending', extraction_method: 'embedded',
  extraction_status: 'success', text_length: 40, confidence_score: null,
  raw_text: 'தமிழ் மொழி', cleaned_text: 'தமிழ் மொழி', warnings: [],
}

function mockBaseline() {
  api.documentCapabilities.mockResolvedValue(CAPABILITIES)
  api.documents.mockResolvedValue({ items: [DOCUMENT] })
  api.documentDetail.mockResolvedValue(DOCUMENT)
  api.documentPages.mockResolvedValue({ items: PAGES })
  api.documentCandidates.mockResolvedValue({ items: [] })
  api.documentJobs.mockResolvedValue({ items: [] })
  api.documentJobEvents.mockResolvedValue({ items: [] })
  api.documentWorkspace.mockResolvedValue(WORKSPACE)
  api.documentPage.mockResolvedValue(PAGE_DETAIL)
  api.documentPageImageUrl.mockResolvedValue('blob:mock-page-image')
  api.documentPageRevisions.mockResolvedValue({ items: [] })
  api.documentPageReviewEvents.mockResolvedValue({ items: [] })
  api.documentPageCleanupSuggestions.mockResolvedValue({ items: [] })
  api.documentRepeatedElements.mockResolvedValue({ items: [] })
  api.documentTamilQualityIssues.mockResolvedValue({ items: [] })
  api.documentTamilQualitySummary.mockResolvedValue({ total_issues: 0, pending_count: 0, by_issue_type: {}, by_review_status: {}, by_correction_risk: {} })
  api.documentSftCandidates.mockResolvedValue({ items: [] })
  api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 0, approved_count: 0, by_task: {}, by_quality_status: {} })
  api.documentSecurityFindings.mockResolvedValue({ items: [] })
  api.documentPiiFindings.mockResolvedValue({ items: [] })
  api.documentContentClassifications.mockResolvedValue({ items: [] })
  api.tamilCorrectionRules.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('DocumentsPage: navigation and overview', () => {
  it('renders all twelve required tabs', async () => {
    mockBaseline()
    render(<DocumentsPage />)
    for (const tab of [
      'Overview', 'Upload', 'Processing', 'Page Review', 'Repeated Elements', 'Tamil Quality',
      'Candidates', 'SFT Candidates', 'Export', 'Security Review', 'Media & Tables', 'Tamil Corrections',
    ]) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview lists uploaded documents with status', async () => {
    mockBaseline()
    render(<DocumentsPage />)
    await waitFor(() => expect(screen.getByText('sample.pdf')).toBeInTheDocument())
    expect(screen.getByText(/2 pages · review_ready/)).toBeInTheDocument()
  })
})

describe('DocumentsPage: upload flow', () => {
  it('submits the upload form and opens the resulting document', async () => {
    mockBaseline()
    api.uploadDocument.mockResolvedValue(DOCUMENT)
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await user.click(screen.getByRole('button', { name: 'Upload' }))
    const file = new File(['%PDF-1.4'], 'sample.pdf', { type: 'application/pdf' })
    const input = screen.getByLabelText('PDF document')
    await user.upload(input, file)
    expect(input.files[0]).toBe(file)
    fireEvent.submit(document.querySelector('form.document-upload'))
    await waitFor(() => expect(api.uploadDocument).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByRole('heading', { name: 'sample.pdf' })).toBeInTheDocument())
  })
})

describe('DocumentsPage: processing tab source & readiness', () => {
  it('shows workspace readiness and wires the link-source action', async () => {
    mockBaseline()
    api.linkDocumentSource.mockResolvedValue({})
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'sample.pdf' })).toBeInTheDocument())
    expect(screen.getByText('Source: unlinked')).toBeInTheDocument()
    expect(screen.getByText('not ready')).toBeInTheDocument()

    const input = screen.getByPlaceholderText(/source public_id/)
    await user.type(input, 'src-42')
    await user.click(screen.getByRole('button', { name: 'Link source' }))
    await waitFor(() => expect(api.linkDocumentSource).toHaveBeenCalledWith('doc-1', 'src-42'))
  })

  it('disables send-to-segmentation while the document is not ready', async () => {
    mockBaseline()
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Source & readiness'))
    expect(screen.getByRole('button', { name: 'Send approved pages to existing segmentation' })).toBeDisabled()
  })
})

describe('DocumentsPage: page review workspace', () => {
  async function openPageOne(user) {
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: /Page 1/ }))
    await waitFor(() => expect(screen.getByText(/PAGE 1/i)).toBeInTheDocument())
  }

  it('renders the original page image and raw/corrected/compare/metadata sub-tabs', async () => {
    mockBaseline()
    const user = userEvent.setup()
    await openPageOne(user)
    expect(screen.getByAltText('Original page 1')).toHaveAttribute('src', 'blob:mock-page-image')
    for (const subtab of ['Raw', 'Corrected', 'Compare', 'Metadata']) {
      expect(screen.getByRole('button', { name: subtab })).toBeInTheDocument()
    }
    expect(screen.getByDisplayValue('தமிழ் மொழி')).toBeInTheDocument()
  })

  it('calls approveDocumentPage when Approve Page is clicked', async () => {
    mockBaseline()
    api.approveDocumentPage.mockResolvedValue({})
    const user = userEvent.setup()
    await openPageOne(user)
    await user.click(screen.getByRole('button', { name: 'Approve Page' }))
    await waitFor(() => expect(api.approveDocumentPage).toHaveBeenCalledWith('doc-1', 1))
  })

  it('saves a corrected-text draft with a change summary', async () => {
    mockBaseline()
    api.editDocumentPage.mockResolvedValue({})
    const user = userEvent.setup()
    await openPageOne(user)
    const textarea = screen.getByLabelText('Corrected text')
    await user.clear(textarea)
    await user.type(textarea, 'திருத்தப்பட்ட உரை')
    await user.type(screen.getByLabelText('Change summary'), 'fixed a typo')
    await user.click(screen.getByRole('button', { name: 'Save Draft' }))
    await waitFor(() => expect(api.editDocumentPage).toHaveBeenCalledWith(
      'doc-1', 1, { cleaned_text: 'திருத்தப்பட்ட உரை', change_summary: 'fixed a typo' },
    ))
  })
})

describe('DocumentsPage: repeated elements review', () => {
  it('detects repeated elements and lets the admin accept a suggestion', async () => {
    mockBaseline()
    api.detectDocumentRepeatedElements.mockResolvedValue({})
    api.reviewDocumentRepeatedElement.mockResolvedValue({})
    const suggestion = { public_id: 'rep-1', element_type: 'header', status: 'suggested', confidence: 0.9, page_occurrences: [1, 2], normalized_text: 'Brud AI corpus' }
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Repeated Elements' }))
    expect(screen.getByText('No repeated-element suggestions yet.')).toBeInTheDocument()

    api.documentRepeatedElements.mockResolvedValue({ items: [suggestion] })
    await user.click(screen.getByRole('button', { name: 'Detect repeated elements' }))
    await waitFor(() => expect(api.detectDocumentRepeatedElements).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByText('Brud AI corpus')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Accept removal' }))
    await waitFor(() => expect(api.reviewDocumentRepeatedElement).toHaveBeenCalledWith('doc-1', 'rep-1', 'accept', {}))
  })
})

describe('DocumentsPage: critical-page filter', () => {
  it('filters the page grid to Tamil-issue pages only', async () => {
    mockBaseline()
    api.documentTamilQualityIssues.mockResolvedValue({
      items: [{ public_id: 'tq-1', page_number: 2, review_status: 'pending', issue_type: 'ocr_character_substitution', correction_risk: 'mechanical', confidence_band: 'high', context: 'x', suggested_text: 'y' }],
    })
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Tamil Quality' }))
    await waitFor(() => expect(api.documentTamilQualityIssues).toHaveBeenCalledWith('doc-1'))
    await user.click(screen.getByRole('button', { name: 'Processing' }))
    await user.click(screen.getByRole('button', { name: 'Tamil issues' }))
    await waitFor(() => expect(screen.getByText('1 of 2 pages shown')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Page 2/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Page 1\b/ })).not.toBeInTheDocument()
  })
})

describe('DocumentsPage: Tamil quality review', () => {
  it('detects issues and accepts a mechanical correction', async () => {
    mockBaseline()
    api.detectDocumentTamilQuality.mockResolvedValue({})
    api.reviewDocumentTamilQualityIssue.mockResolvedValue({})
    const issue = { public_id: 'tq-1', page_number: 1, review_status: 'pending', issue_type: 'ocr_character_substitution', correction_risk: 'mechanical', confidence_band: 'high', context: 'broken text', suggested_text: 'fixed text' }
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Tamil Quality' }))
    expect(screen.getByText('No Tamil quality issues detected yet.')).toBeInTheDocument()

    api.documentTamilQualityIssues.mockResolvedValue({ items: [issue] })
    api.documentTamilQualitySummary.mockResolvedValue({ total_issues: 1, pending_count: 1, by_issue_type: {}, by_review_status: {}, by_correction_risk: { mechanical: 1 } })
    await user.click(screen.getByRole('button', { name: 'Detect Tamil quality issues' }))
    await waitFor(() => expect(api.detectDocumentTamilQuality).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByText('broken text')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(api.reviewDocumentTamilQualityIssue).toHaveBeenCalledWith('doc-1', 'tq-1', { action: 'accept' }))
  })

  it('disables Accept for a mandatory-review issue', async () => {
    mockBaseline()
    const issue = { public_id: 'tq-2', page_number: 1, review_status: 'pending', issue_type: 'invalid_unicode', correction_risk: 'mandatory_review', confidence_band: 'high', context: 'broken text', suggested_text: '' }
    api.documentTamilQualityIssues.mockResolvedValue({ items: [issue] })
    api.documentTamilQualitySummary.mockResolvedValue({ total_issues: 1, pending_count: 1, by_issue_type: {}, by_review_status: {}, by_correction_risk: { mandatory_review: 1 } })
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Tamil Quality' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Accept' })).toBeDisabled())
  })
})

describe('DocumentsPage: SFT candidate review', () => {
  it('generates candidates and approves one with verified rights', async () => {
    mockBaseline()
    api.generateDocumentSftCandidates.mockResolvedValue({})
    api.reviewDocumentSftCandidate.mockResolvedValue({})
    const candidate = {
      public_id: 'sft-1', task: 'definition', source_page_start: 1, source_page_end: 1,
      quality_status: 'pending_review', rights_status: 'verified', generation_method: 'template_heuristic_v1',
      instruction: 'Explain the term.', response: 'A definition.',
    }
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'SFT Candidates' }))
    expect(screen.getByText('No SFT candidates yet. Approve chunks, then generate candidates.')).toBeInTheDocument()

    api.documentSftCandidates.mockResolvedValue({ items: [candidate] })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 1, approved_count: 0, by_task: { definition: 1 }, by_quality_status: { pending_review: 1 } })
    await user.click(screen.getByRole('button', { name: 'Generate SFT candidates' }))
    await waitFor(() => expect(api.generateDocumentSftCandidates).toHaveBeenCalledWith('doc-1', {}))
    await waitFor(() => expect(screen.getByText('A definition.')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.reviewDocumentSftCandidate).toHaveBeenCalledWith('doc-1', 'sft-1', { action: 'approve' }))
  })

  it('blocks Approve when rights are not verified', async () => {
    mockBaseline()
    const candidate = {
      public_id: 'sft-2', task: 'definition', source_page_start: 1, source_page_end: 1,
      quality_status: 'pending_review', rights_status: 'pending', generation_method: 'template_heuristic_v1',
      instruction: 'Explain.', response: 'Text.',
    }
    api.documentSftCandidates.mockResolvedValue({ items: [candidate] })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 1, approved_count: 0, by_task: {}, by_quality_status: { pending_review: 1 } })
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'SFT Candidates' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled())
    expect(screen.getByText(/Rights not verified/)).toBeInTheDocument()
  })
})

describe('DocumentsPage: SFT export', () => {
  it('exports approved candidates and shows the manifest summary', async () => {
    mockBaseline()
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 1, approved_count: 1, by_task: {}, by_quality_status: { approved: 1 } })
    api.exportDocumentSftCandidates.mockResolvedValue({
      public_id: 'export-1', record_count: 1, excluded_count: 0, task_distribution: { definition: 1 },
      checksum_sha256: 'a'.repeat(64), export_path: 'export-1.jsonl',
    })
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Export' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export 1 approved candidate(s)' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Export 1 approved candidate(s)' }))
    await waitFor(() => expect(api.exportDocumentSftCandidates).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByText('Export export-1')).toBeInTheDocument())
  })
})

describe('DocumentsPage: security review', () => {
  it('scans for findings and marks a pending finding reviewed', async () => {
    mockBaseline()
    api.scanDocumentSecurityFindings.mockResolvedValue({})
    api.reviewDocumentSecurityFinding.mockResolvedValue({})
    const finding = {
      public_id: 'sec-1', finding_type: 'pii_email', page_number: 1, matched_text: 'a@b.com',
      confidence_band: 'high', reason_code: 'email_pattern_detected', action: 'require_review',
      review_status: 'pending',
    }
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Security Review' }))
    expect(screen.getByText('No security findings yet. Run a scan.')).toBeInTheDocument()

    api.documentSecurityFindings.mockResolvedValue({ items: [finding] })
    api.documentPiiFindings.mockResolvedValue({ items: [finding] })
    await user.click(screen.getByRole('button', { name: 'Scan for security & PII findings' }))
    await waitFor(() => expect(api.scanDocumentSecurityFindings).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByText('pii email')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Mark reviewed' }))
    await waitFor(() => expect(api.reviewDocumentSecurityFinding).toHaveBeenCalledWith('doc-1', 'sec-1', 'reviewed'))
  })

  it('shows an export-blocked warning for a secret/path finding', async () => {
    mockBaseline()
    const finding = {
      public_id: 'sec-2', finding_type: 'pii_secret', page_number: 1, matched_text: 'sk-secretvalue',
      confidence_band: 'high', reason_code: 'secret_like_content_detected', action: 'block_export',
      review_status: 'pending',
    }
    api.documentSecurityFindings.mockResolvedValue({ items: [finding] })
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Security Review' }))
    await waitFor(() => expect(screen.getByText(/Export blocked/)).toBeInTheDocument())
  })
})

describe('DocumentsPage: media & table classification', () => {
  it('scans pages and flags vision_required content as blocked from text-only SFT', async () => {
    mockBaseline()
    api.scanDocumentContentClassifications.mockResolvedValue({})
    const classification = {
      public_id: 'cls-1', page_number: 1, content_type: 'image_without_usable_text',
      caption_text: '', vision_required: true, review_status: 'pending',
    }
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Media & Tables' }))
    expect(screen.getByText('No classifications yet. Run a scan.')).toBeInTheDocument()

    api.documentContentClassifications.mockResolvedValue({ items: [classification] })
    await user.click(screen.getByRole('button', { name: 'Classify pages' }))
    await waitFor(() => expect(api.scanDocumentContentClassifications).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByText(/require a Vision model/)).toBeInTheDocument())
    expect(screen.getByText('vision_required')).toBeInTheDocument()
  })
})

describe('DocumentsPage: Tamil correction rules', () => {
  it('creates a draft rule and cannot skip straight to activation', async () => {
    mockBaseline()
    const rule = {
      public_id: 'rule-1', incorrect_form: 'a', approved_correction: 'b', status: 'draft',
      rule_version: 1, meaning_change_risk: 'mechanical', issue_category: 'pulli_error',
      confidence_band: 'high', automatic_proposal_allowed: true,
    }
    api.createTamilCorrectionRule.mockResolvedValue(rule)
    const user = userEvent.setup()
    render(<DocumentsPage />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    await user.click(screen.getByRole('button', { name: 'Tamil Corrections' }))
    expect(screen.getByText('No Tamil correction rules yet.')).toBeInTheDocument()

    api.tamilCorrectionRules.mockResolvedValue({ items: [rule] })
    await user.type(screen.getByLabelText('Incorrect form'), 'a')
    await user.type(screen.getByLabelText('Approved correction'), 'b')
    await user.click(screen.getByRole('button', { name: 'Create draft rule' }))
    await waitFor(() => expect(api.createTamilCorrectionRule).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText('a → b')).toBeInTheDocument())

    expect(screen.getByRole('button', { name: 'submit review' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'activate' })).not.toBeInTheDocument()
  })
})

describe('DocumentsPage: deep-link navigation', () => {
  it('opens the requested document and semantic tab on initial load', async () => {
    mockBaseline()
    render(<DocumentsPage initialDocumentPublicId="doc-1" initialTab="security-review" />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Security Review', exact: true }).className).toContain('active'))
    await waitFor(() => expect(api.documentDetail).toHaveBeenCalledWith('doc-1'))
  })

  it('sets the Critical only page filter when the critical-pages semantic key is requested', async () => {
    mockBaseline()
    render(<DocumentsPage initialDocumentPublicId="doc-1" initialTab="critical-pages" />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Processing', exact: true }).className).toContain('active'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Critical only' }).className).toContain('active'))
  })

  it('falls back to a safe default tab with a non-fatal notice for an unknown tab key', async () => {
    mockBaseline()
    render(<DocumentsPage initialDocumentPublicId="doc-1" initialTab="not-a-real-tab" />)
    await waitFor(() => expect(screen.getByText(/requested tab is unavailable/)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Overview', exact: true }).className).toContain('active')
  })

  it('shows a stable not-found state for an unknown document public ID', async () => {
    mockBaseline()
    render(<DocumentsPage initialDocumentPublicId="doc-does-not-exist" initialTab="security-review" />)
    await waitFor(() => expect(screen.getByText(/requested document was not found/)).toBeInTheDocument())
    expect(screen.getByText('sample.pdf')).toBeInTheDocument()
  })

  it('calls onNavigationChange when the admin switches tabs, keeping deep-link state in sync', async () => {
    mockBaseline()
    const onNavigationChange = vi.fn()
    const user = userEvent.setup()
    render(<DocumentsPage onNavigationChange={onNavigationChange} />)
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText('Pages'))
    onNavigationChange.mockClear()
    await user.click(screen.getByRole('button', { name: 'Security Review' }))
    expect(onNavigationChange).toHaveBeenCalledWith('doc-1', 'Security Review')
  })
})
