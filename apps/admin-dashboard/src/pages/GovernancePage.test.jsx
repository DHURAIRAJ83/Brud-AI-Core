import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GovernancePage from './GovernancePage.jsx'

vi.mock('../services/api.js', () => ({
  addGovernanceReviewItemNote: vi.fn(), assessGovernanceQuality: vi.fn(), assignGovernanceReviewItem: vi.fn(),
  evaluateGovernanceApproval: vi.fn(), governanceApprovalStatus: vi.fn(), governanceConflictGroups: vi.fn(),
  governanceDuplicateGroups: vi.fn(), governanceExportReadiness: vi.fn(), governanceQueue: vi.fn(),
  governanceReviewItem: vi.fn(), governanceReviewItemHistory: vi.fn(), openGovernanceReviewItem: vi.fn(),
  overrideGovernanceApproval: vi.fn(), resolveGovernanceConflictGroup: vi.fn(), resolveGovernanceDuplicateGroup: vi.fn(),
  setGovernanceReviewItemStatus: vi.fn(), syncChunkDuplicate: vi.fn(), syncManualDataDuplicate: vi.fn(),
  syncStructuredRecordConflict: vi.fn(),
}))

const api = await import('../services/api.js')

const REVIEW_ITEM = {
  public_id: 'rev-1', review_code: 'REV-0001', entity_type: 'manual_data_record',
  entity_public_id: 'mdr-1', status: 'open', priority: 'high', assigned_admin_public_id: null,
}

function mockBaseline() {
  api.governanceQueue.mockResolvedValue({ items: [REVIEW_ITEM], counts_by_status: { open: 1 } })
  api.governanceDuplicateGroups.mockResolvedValue({ items: [] })
  api.governanceConflictGroups.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('GovernancePage: navigation', () => {
  it('renders all nine required tabs', async () => {
    mockBaseline()
    render(<GovernancePage />)
    for (const tab of [
      'Overview', 'Queue', 'Review Detail', 'Quality', 'Duplicates', 'Conflicts',
      'Approvals', 'Export Readiness', 'History',
    ]) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview shows the queue status counts, including zero states', async () => {
    mockBaseline()
    render(<GovernancePage />)
    await waitFor(() => expect(screen.getByText('open').nextSibling).toHaveTextContent('1'))
    expect(screen.getByText('resolved').nextSibling).toHaveTextContent('0')
  })
})

describe('GovernancePage: queue', () => {
  it('lists open review items and opens one into Review Detail', async () => {
    mockBaseline()
    api.governanceReviewItem.mockResolvedValue({ ...REVIEW_ITEM, issues: [], target_approvals: [] })
    const user = userEvent.setup()
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Queue' }))
    await waitFor(() => screen.getByText('REV-0001'))
    await user.click(screen.getByText('Open'))
    await waitFor(() => expect(api.governanceReviewItem).toHaveBeenCalledWith('rev-1'))
    expect(screen.getByRole('button', { name: 'Review Detail' })).toHaveClass('active')
  })

  it('opening a review item manually calls openGovernanceReviewItem with the entered fields', async () => {
    mockBaseline()
    api.openGovernanceReviewItem.mockResolvedValue({ public_id: 'rev-2' })
    api.governanceReviewItem.mockResolvedValue({ ...REVIEW_ITEM, public_id: 'rev-2', issues: [], target_approvals: [] })
    const user = userEvent.setup()
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Queue' }))
    await waitFor(() => screen.getByText('Open a review item manually'))
    await user.type(screen.getByLabelText('Entity public id'), 'page-9')
    await user.click(screen.getByRole('button', { name: 'Open review item' }))
    await waitFor(() => expect(api.openGovernanceReviewItem).toHaveBeenCalled())
    const call = api.openGovernanceReviewItem.mock.calls[0][0]
    expect(call.entity_public_id).toBe('page-9')
  })
})

describe('GovernancePage: review detail actions', () => {
  async function openDetail(user) {
    api.governanceReviewItem.mockResolvedValue({ ...REVIEW_ITEM, issues: [], target_approvals: [] })
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Queue' }))
    await waitFor(() => screen.getByText('REV-0001'))
    await user.click(screen.getByText('Open'))
    await waitFor(() => screen.getByText('REV-0001'))
  }

  it('assign calls assignGovernanceReviewItem with the review id and assignee', async () => {
    mockBaseline()
    api.assignGovernanceReviewItem.mockResolvedValue({ ...REVIEW_ITEM, assigned_admin_public_id: 'admin-2' })
    const user = userEvent.setup()
    await openDetail(user)
    const assignInput = screen.getByPlaceholderText('admin public id')
    await user.type(assignInput, 'admin-2')
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    await waitFor(() => expect(api.assignGovernanceReviewItem).toHaveBeenCalledWith('rev-1', 'admin-2'))
  })

  it('add note calls addGovernanceReviewItemNote with the review id and note text', async () => {
    mockBaseline()
    api.addGovernanceReviewItemNote.mockResolvedValue({})
    const user = userEvent.setup()
    await openDetail(user)
    const noteInput = screen.getAllByRole('textbox').at(-1)
    await user.type(noteInput, 'checked and fine')
    await user.click(screen.getByRole('button', { name: 'Add note' }))
    await waitFor(() => expect(api.addGovernanceReviewItemNote).toHaveBeenCalledWith('rev-1', 'checked and fine'))
  })
})

describe('GovernancePage: quality assessment', () => {
  it('assess calls assessGovernanceQuality with the entered entity type and id', async () => {
    mockBaseline()
    api.assessGovernanceQuality.mockResolvedValue({
      normalized_quality: { is_blocked: true, overall_score: 40, blocking_issue_codes: ['HIGH_RISK_UNVERIFIED'] },
      review_item: { review_code: 'REV-0050', status: 'open' },
    })
    const user = userEvent.setup()
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Quality' }))
    await waitFor(() => screen.getByText(/Assess an entity/))
    await user.type(screen.getByRole('textbox'), 'mdr-9')
    await user.click(screen.getByRole('button', { name: 'Run quality assessment' }))
    await waitFor(() => expect(api.assessGovernanceQuality).toHaveBeenCalledWith('manual_data_record', 'mdr-9'))
    await waitFor(() => screen.getByText(/Blocked: yes/))
  })
})

describe('GovernancePage: approvals', () => {
  it('override requires a non-empty reason before the button is enabled', async () => {
    mockBaseline()
    const user = userEvent.setup()
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Approvals' }))
    await waitFor(() => screen.getByText('Admin override'))
    const entityInputs = screen.getAllByRole('textbox')
    await user.type(entityInputs[0], 'mdr-5')
    const overrideButton = screen.getByRole('button', { name: 'Override' })
    expect(overrideButton).toBeDisabled()
    await user.type(screen.getByPlaceholderText('override reason (required)'), 'legal cleared this')
    expect(overrideButton).not.toBeDisabled()
  })

  it('override calls overrideGovernanceApproval with the entity, target use, decision and reason', async () => {
    mockBaseline()
    api.overrideGovernanceApproval.mockResolvedValue({ decision: 'allowed', decision_code: 'ADMIN_OVERRIDE' })
    api.governanceApprovalStatus.mockResolvedValue({ targets: {} })
    const user = userEvent.setup()
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Approvals' }))
    await waitFor(() => screen.getByText('Admin override'))
    const entityInputs = screen.getAllByRole('textbox')
    await user.type(entityInputs[0], 'mdr-5')
    await user.type(screen.getByPlaceholderText('override reason (required)'), 'legal cleared this')
    await user.click(screen.getByRole('button', { name: 'Override' }))
    await waitFor(() => expect(api.overrideGovernanceApproval).toHaveBeenCalledWith(
      'manual_data_record', 'mdr-5', 'training', { decision: 'allowed', reason: 'legal cleared this' },
    ))
  })
})

describe('GovernancePage: export readiness', () => {
  it('checking readiness calls governanceExportReadiness and shows the decision', async () => {
    mockBaseline()
    api.governanceExportReadiness.mockResolvedValue({
      decision: 'blocked', decision_code: 'BLOCKED_QUALITY_ISSUE', blocking_issue_ids: ['iss-1'], required_actions: [],
    })
    const user = userEvent.setup()
    render(<GovernancePage />)
    await user.click(screen.getByRole('button', { name: 'Export Readiness' }))
    await waitFor(() => screen.getByText(/Export \/ RAG-handoff readiness/))
    await user.type(screen.getAllByRole('textbox')[0], 'sr-1')
    await user.click(screen.getByRole('button', { name: 'Check readiness' }))
    await waitFor(() => expect(api.governanceExportReadiness).toHaveBeenCalledWith(
      'structured_record_candidate', 'sr-1', 'dataset_export',
    ))
    await waitFor(() => screen.getByText(/Decision: blocked/))
  })
})
