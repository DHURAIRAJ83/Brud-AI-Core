import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ManualDataPage from './ManualDataPage.jsx'

vi.mock('../services/api.js', () => ({
  manualDataRecords: vi.fn(),
  manualDataSummary: vi.fn(),
  createManualDataRecord: vi.fn(),
  manualDataRecord: vi.fn(),
  createManualDataRevision: vi.fn(),
  archiveManualDataRecord: vi.fn(),
  restoreManualDataRecord: vi.fn(),
  submitManualDataForReview: vi.fn(),
  requestManualDataCorrection: vi.fn(),
  requestManualDataSourceVerification: vi.fn(),
  requestManualDataDomainReview: vi.fn(),
  submitManualDataReview: vi.fn(),
  manualDataReviews: vi.fn(),
  submitManualDataVerification: vi.fn(),
  manualDataVerifications: vi.fn(),
  approveManualDataRecord: vi.fn(),
  rejectManualDataRecord: vi.fn(),
  manualDataQualityCheck: vi.fn(),
  manualDataDuplicateCheck: vi.fn(),
  manualDataUsageSummary: vi.fn(),
  manualDataHistory: vi.fn(),
  createManualDataDatasetCandidate: vi.fn(),
}))

const api = await import('../services/api.js')

const RECORD_DRAFT = {
  public_id: 'rec-1', record_code: 'MD-0001', record_type: 'plain_text', status: 'draft',
  source_public_id: 'src-1', source_title: 'Dhurai -- Spoken Tamil',
}
const RECORD_NEEDS_REVIEW = {
  public_id: 'rec-2', record_code: 'MD-0002', record_type: 'dictionary_entry', status: 'needs_review',
  source_public_id: 'src-1', source_title: 'Dhurai -- Spoken Tamil',
}
const RECORD_APPROVED = {
  public_id: 'rec-3', record_code: 'MD-0003', record_type: 'plain_text', status: 'approved',
  approved_uses: ['rag'], source_public_id: 'src-1', source_title: 'Dhurai -- Spoken Tamil',
}
const RECORD_REJECTED = {
  public_id: 'rec-4', record_code: 'MD-0004', record_type: 'plain_text', status: 'rejected',
  source_public_id: 'src-1', source_title: 'Dhurai -- Spoken Tamil',
}

function mockList(items) {
  api.manualDataRecords.mockResolvedValue({ items, total: items.length, page: 1, page_size: 100, total_pages: 1 })
}

function mockSummary(byStatus = {}) {
  api.manualDataSummary.mockResolvedValue({
    total: Object.values(byStatus).reduce((a, b) => a + b, 0),
    by_status: byStatus, by_record_type: {}, by_primary_language: {}, by_creation_method: {},
  })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('ManualDataPage: navigation and overview', () => {
  it('renders all eight required tabs', async () => {
    mockList([])
    mockSummary()
    render(<ManualDataPage />)
    for (const tab of ['Overview', 'Create Data', 'Records', 'Review Queue', 'Verification Queue', 'Approved', 'Rejected', 'History']) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview shows real persisted counts, including zero states', async () => {
    mockList([RECORD_DRAFT, RECORD_NEEDS_REVIEW])
    mockSummary({ draft: 1, needs_review: 1 })
    render(<ManualDataPage />)
    await waitFor(() => expect(screen.getByText('Total manual records').nextSibling).toHaveTextContent('2'))
    expect(screen.getByText('draft').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('approved').nextSibling).toHaveTextContent('0')
  })
})

describe('ManualDataPage: Create Data tab', () => {
  it('creates a plain-text record against an existing source', async () => {
    mockList([])
    mockSummary()
    api.createManualDataRecord.mockResolvedValue({ ...RECORD_DRAFT })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Create Data' }))
    await user.type(screen.getByLabelText('Source public id'), 'src-1')
    await user.type(screen.getByLabelText('Tamil text'), 'வணக்கம்')
    mockList([RECORD_DRAFT])
    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(api.createManualDataRecord).toHaveBeenCalledWith(
      expect.objectContaining({ record_type: 'plain_text', source_public_id: 'src-1' })
    )
  })

  it('shows dictionary-specific fields only when dictionary_entry is selected', async () => {
    mockList([])
    mockSummary()
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Create Data' }))
    expect(screen.queryByLabelText('Word')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Data type'), 'dictionary_entry')
    expect(screen.getByLabelText('Word')).toBeInTheDocument()
    expect(screen.getByLabelText('Meanings (one per line)')).toBeInTheDocument()
  })

  it('shows conversation turn editor for conversation type', async () => {
    mockList([])
    mockSummary()
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Create Data' }))
    await user.selectOptions(screen.getByLabelText('Data type'), 'conversation')
    await user.click(screen.getByRole('button', { name: 'Add turn' }))
    expect(screen.getByPlaceholderText('Turn content')).toBeInTheDocument()
  })
})

describe('ManualDataPage: Records tab', () => {
  it('lists records and archives one', async () => {
    mockList([RECORD_DRAFT])
    mockSummary({ draft: 1 })
    api.archiveManualDataRecord.mockResolvedValue({ ...RECORD_DRAFT, status: 'archived' })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Records' }))
    await waitFor(() => expect(screen.getByText('MD-0001')).toBeInTheDocument())
    mockList([{ ...RECORD_DRAFT, status: 'archived' }])
    await user.click(screen.getByRole('button', { name: 'Archive' }))
    expect(api.archiveManualDataRecord).toHaveBeenCalledWith('rec-1')
  })
})

describe('ManualDataPage: Review Queue tab', () => {
  it('runs a quality check and shows blocking issues', async () => {
    mockList([RECORD_NEEDS_REVIEW])
    mockSummary({ needs_review: 1 })
    api.manualDataRecord.mockResolvedValue({ ...RECORD_NEEDS_REVIEW, active_revision: { word: 'நல்லது' } })
    api.manualDataReviews.mockResolvedValue({ items: [] })
    api.manualDataVerifications.mockResolvedValue({ items: [] })
    api.manualDataQualityCheck.mockResolvedValue({
      overall_score: 40, blocking_issues: ['MISSING_SOURCE'], warnings: [], recommended_status: 'draft',
    })
    api.manualDataDuplicateCheck.mockResolvedValue({ duplicate_status: 'unique' })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Review Queue' }))
    await user.selectOptions(screen.getByLabelText('Record'), 'rec-2')
    await waitFor(() => expect(within(document.querySelector('.history-panel')).getByText(/MD-0002/)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Run quality & duplicate check' }))
    await waitFor(() => expect(screen.getByText('MISSING_SOURCE')).toBeInTheDocument())
  })

  it('submits a review with scores', async () => {
    mockList([RECORD_NEEDS_REVIEW])
    mockSummary({ needs_review: 1 })
    api.manualDataRecord.mockResolvedValue({ ...RECORD_NEEDS_REVIEW, active_revision: {} })
    api.manualDataReviews.mockResolvedValue({ items: [] })
    api.manualDataVerifications.mockResolvedValue({ items: [] })
    api.submitManualDataReview.mockResolvedValue({})
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Review Queue' }))
    await user.selectOptions(screen.getByLabelText('Record'), 'rec-2')
    await waitFor(() => expect(within(document.querySelector('.history-panel')).getByText(/MD-0002/)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Submit review' }))
    expect(api.submitManualDataReview).toHaveBeenCalledWith('rec-2', expect.objectContaining({ review_type: 'language' }))
  })

  it('approves for explicitly selected uses only, never one global approve', async () => {
    mockList([RECORD_NEEDS_REVIEW])
    mockSummary({ needs_review: 1 })
    api.manualDataRecord.mockResolvedValue({ ...RECORD_NEEDS_REVIEW, active_revision: {} })
    api.manualDataReviews.mockResolvedValue({ items: [] })
    api.manualDataVerifications.mockResolvedValue({ items: [] })
    api.approveManualDataRecord.mockResolvedValue({ ...RECORD_NEEDS_REVIEW, status: 'approved', approved_uses: ['rag'] })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Review Queue' }))
    await user.selectOptions(screen.getByLabelText('Record'), 'rec-2')
    await waitFor(() => expect(within(document.querySelector('.history-panel')).getByText(/MD-0002/)).toBeInTheDocument())
    const useGrid = screen.getByText('rag').closest('label')
    await user.click(within(useGrid).getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Approve for selected uses' }))
    expect(api.approveManualDataRecord).toHaveBeenCalledWith('rec-2', { approved_uses: ['rag'] })
  })

  it('rejects a record with a reason', async () => {
    mockList([RECORD_NEEDS_REVIEW])
    mockSummary({ needs_review: 1 })
    api.manualDataRecord.mockResolvedValue({ ...RECORD_NEEDS_REVIEW, active_revision: {} })
    api.manualDataReviews.mockResolvedValue({ items: [] })
    api.manualDataVerifications.mockResolvedValue({ items: [] })
    api.rejectManualDataRecord.mockResolvedValue({ ...RECORD_NEEDS_REVIEW, status: 'rejected' })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Review Queue' }))
    await user.selectOptions(screen.getByLabelText('Record'), 'rec-2')
    await waitFor(() => expect(within(document.querySelector('.history-panel')).getByText(/MD-0002/)).toBeInTheDocument())
    await user.type(screen.getByLabelText('Rejection reason'), 'not natural')
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    expect(api.rejectManualDataRecord).toHaveBeenCalledWith('rec-2', { reason: 'not natural' })
  })
})

describe('ManualDataPage: Verification Queue tab', () => {
  it('records a verification decision with an optional supporting source', async () => {
    const needsVerification = { ...RECORD_NEEDS_REVIEW, public_id: 'rec-5', record_code: 'MD-0005', status: 'needs_source_verification' }
    mockList([needsVerification])
    mockSummary({ needs_source_verification: 1 })
    api.manualDataRecord.mockResolvedValue({ ...needsVerification, active_revision: {} })
    api.manualDataReviews.mockResolvedValue({ items: [] })
    api.manualDataVerifications.mockResolvedValue({ items: [] })
    api.submitManualDataVerification.mockResolvedValue({})
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Verification Queue' }))
    await user.selectOptions(screen.getByLabelText('Record'), 'rec-5')
    await waitFor(() => expect(within(document.querySelector('.history-panel')).getByText(/MD-0005/)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Record verification' }))
    expect(api.submitManualDataVerification).toHaveBeenCalledWith(
      'rec-5', expect.objectContaining({ verification_type: 'factual_verification' })
    )
  })
})

describe('ManualDataPage: Approved tab', () => {
  it('creates a dataset candidate for an approved record', async () => {
    mockList([RECORD_APPROVED])
    mockSummary({ approved: 1 })
    api.createManualDataDatasetCandidate.mockResolvedValue({ exported_dataset_record_public_id: 'dr-1' })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Approved' }))
    await waitFor(() => expect(screen.getByText('MD-0003')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Create Dataset Candidate' }))
    expect(api.createManualDataDatasetCandidate).toHaveBeenCalledWith('rec-3', expect.any(Object))
  })
})

describe('ManualDataPage: Rejected tab', () => {
  it('lists only rejected records', async () => {
    mockList([RECORD_DRAFT, RECORD_REJECTED])
    mockSummary({ draft: 1, rejected: 1 })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'Rejected' }))
    expect(screen.getByText('MD-0004')).toBeInTheDocument()
    expect(screen.queryByText('MD-0001')).not.toBeInTheDocument()
  })
})

describe('ManualDataPage: History tab', () => {
  it('shows revisions, events, and the usage-eligibility grid', async () => {
    mockList([RECORD_DRAFT])
    mockSummary({ draft: 1 })
    api.manualDataRecord.mockResolvedValue({ ...RECORD_DRAFT, active_revision: {} })
    api.manualDataReviews.mockResolvedValue({ items: [] })
    api.manualDataVerifications.mockResolvedValue({ items: [] })
    api.manualDataHistory.mockResolvedValue({
      revisions: [{ public_id: 'rev-1', revision_number: 1, change_summary: 'initial draft', created_at: '2026-01-01' }],
      events: [{ public_id: 'evt-1', event_type: 'record_created', status_before: null, status_after: 'draft', created_at: '2026-01-01' }],
    })
    api.manualDataUsageSummary.mockResolvedValue({
      rag: { allowed: false }, training: { allowed: false }, evaluation: { allowed: false },
      commercial: { allowed: false }, public_export: { allowed: false }, redistribution: { allowed: false },
    })
    const user = userEvent.setup()
    render(<ManualDataPage />)
    await user.click(screen.getByRole('button', { name: 'History' }))
    await user.selectOptions(screen.getByLabelText('Record'), 'rec-1')
    await user.click(screen.getByRole('button', { name: 'Load history' }))
    await waitFor(() => expect(screen.getByText(/initial draft/)).toBeInTheDocument())
    expect(screen.getByText(/record_created/)).toBeInTheDocument()
    const grid = document.querySelector('.metric-grid')
    expect(within(grid).getByText('rag').nextSibling).toHaveTextContent('Blocked')
  })
})
