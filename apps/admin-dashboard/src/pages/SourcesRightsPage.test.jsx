import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SourcesRightsPage from './SourcesRightsPage.jsx'

vi.mock('../services/api.js', () => ({
  dataSources: vi.fn(),
  createDataSource: vi.fn(),
  dataSource: vi.fn(),
  archiveDataSource: vi.fn(),
  restoreDataSource: vi.fn(),
  dataSourceRights: vi.fn(),
  upsertDataSourceRights: vi.fn(),
  submitDataSourceForReview: vi.fn(),
  verifyDataSource: vi.fn(),
  restrictDataSource: vi.fn(),
  rejectDataSource: vi.fn(),
  checkDataSourceUsage: vi.fn(),
  dataSourceUsageSummary: vi.fn(),
  dataSourceHistory: vi.fn(),
  dataSourceVerificationEvents: vi.fn(),
}))

const api = await import('../services/api.js')

const SOURCE_DRAFT = {
  public_id: 'src-1', source_code: 'SRC-HUMAN-0001', title: 'Spoken Tamil', source_type: 'human_created', status: 'draft',
}
const SOURCE_REJECTED = {
  public_id: 'src-2', source_code: 'SRC-WEB-0001', title: 'Random blog', source_type: 'web_source', status: 'rejected',
}

function mockList(items) {
  api.dataSources.mockResolvedValue({ items, total: items.length, page: 1, page_size: 100, total_pages: 1 })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('SourcesRightsPage: navigation and overview', () => {
  it('renders all six required tabs', async () => {
    mockList([])
    render(<SourcesRightsPage />)
    for (const tab of ['Overview', 'Sources', 'Rights Review', 'Usage Eligibility', 'Verification History', 'Blocked Items']) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview counts sources by status honestly, including zero states', async () => {
    mockList([SOURCE_DRAFT, SOURCE_REJECTED])
    render(<SourcesRightsPage />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('2'))
    expect(screen.getByText('draft').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('rejected').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('verified').nextSibling).toHaveTextContent('0')
  })
})

describe('SourcesRightsPage: Sources tab', () => {
  it('creates a source and refreshes the list', async () => {
    mockList([])
    api.createDataSource.mockResolvedValue({ ...SOURCE_DRAFT })
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Sources' }))
    await user.type(screen.getByLabelText('Source code'), 'SRC-HUMAN-0001')
    await user.type(screen.getByLabelText('Title'), 'Spoken Tamil')
    mockList([SOURCE_DRAFT])
    await user.click(screen.getByRole('button', { name: 'Create draft source' }))
    expect(api.createDataSource).toHaveBeenCalledWith(
      expect.objectContaining({ source_code: 'SRC-HUMAN-0001', title: 'Spoken Tamil', source_type: 'human_created' })
    )
    await waitFor(() => expect(screen.getByText('SRC-HUMAN-0001')).toBeInTheDocument())
  })

  it('archiving a source calls the API and reloads the list', async () => {
    mockList([SOURCE_DRAFT])
    api.archiveDataSource.mockResolvedValue({ ...SOURCE_DRAFT, status: 'archived' })
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Sources' }))
    await waitFor(() => expect(screen.getByText('SRC-HUMAN-0001')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Archive' }))
    expect(api.archiveDataSource).toHaveBeenCalledWith('src-1')
  })
})

describe('SourcesRightsPage: Rights Review tab', () => {
  it('loads existing rights when a source is selected and saves an updated declaration', async () => {
    mockList([SOURCE_DRAFT])
    api.dataSourceRights.mockResolvedValue(null)
    api.upsertDataSourceRights.mockResolvedValue({})
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Rights Review' }))
    await waitFor(() => expect(screen.getByLabelText('Source to review')).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Source to review'), 'src-1')
    await waitFor(() => expect(api.dataSourceRights).toHaveBeenCalledWith('src-1'))

    await user.selectOptions(screen.getByLabelText('Rights status'), 'licensed')
    await user.click(screen.getByLabelText('Training'))
    await user.click(screen.getByRole('button', { name: 'Save rights declaration' }))

    expect(api.upsertDataSourceRights).toHaveBeenCalledWith(
      'src-1',
      expect.objectContaining({ rights_status: 'licensed', training_use_allowed: true })
    )
  })

  it('exposes six explicit per-use checkboxes, never one ambiguous approved toggle', async () => {
    mockList([SOURCE_DRAFT])
    api.dataSourceRights.mockResolvedValue(null)
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Rights Review' }))
    await user.selectOptions(screen.getByLabelText('Source to review'), 'src-1')
    for (const label of ['RAG', 'Training', 'Evaluation', 'Commercial use', 'Public export', 'Redistribution']) {
      expect(screen.getByLabelText(label)).toHaveAttribute('type', 'checkbox')
    }
    expect(screen.queryByLabelText(/^approved$/i)).not.toBeInTheDocument()
  })

  it('records a verification decision via the review-actions panel', async () => {
    mockList([SOURCE_DRAFT])
    api.dataSourceRights.mockResolvedValue(null)
    api.verifyDataSource.mockResolvedValue({})
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Rights Review' }))
    await user.selectOptions(screen.getByLabelText('Source to review'), 'src-1')
    await user.click(screen.getByRole('button', { name: 'Verify (document)' }))
    expect(api.verifyDataSource).toHaveBeenCalledWith('src-1', expect.objectContaining({ action: 'document_verify' }))
  })
})

describe('SourcesRightsPage: Usage Eligibility tab', () => {
  it('shows an honest blocked decision with reasons', async () => {
    mockList([SOURCE_DRAFT])
    api.dataSourceRights.mockResolvedValue(null)
    api.checkDataSourceUsage.mockResolvedValue({
      allowed: false, decision_code: 'BLOCKED_RIGHTS_UNKNOWN',
      blocking_reasons: ['rights_unknown'], warnings: [], required_actions: ['Declare rights.'],
    })
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Usage Eligibility' }))
    await user.selectOptions(screen.getByLabelText('Source'), 'src-1')
    await user.click(screen.getByRole('button', { name: 'Check eligibility' }))
    await waitFor(() => expect(screen.getByText('Blocked')).toBeInTheDocument())
    expect(screen.getByText('rights_unknown')).toBeInTheDocument()
  })

  it('shows an allowed decision once rights permit it', async () => {
    mockList([SOURCE_DRAFT])
    api.dataSourceRights.mockResolvedValue(null)
    api.checkDataSourceUsage.mockResolvedValue({
      allowed: true, decision_code: 'ALLOWED', blocking_reasons: [], warnings: [], required_actions: [],
    })
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Usage Eligibility' }))
    await user.selectOptions(screen.getByLabelText('Source'), 'src-1')
    await user.click(screen.getByRole('button', { name: 'Check eligibility' }))
    await waitFor(() => expect(screen.getByText('Allowed')).toBeInTheDocument())
  })

  it('shows every target use at a glance', async () => {
    mockList([SOURCE_DRAFT])
    api.dataSourceRights.mockResolvedValue(null)
    api.dataSourceUsageSummary.mockResolvedValue({
      rag: { allowed: true }, training: { allowed: false }, evaluation: { allowed: false },
      commercial: { allowed: false }, public_export: { allowed: false }, redistribution: { allowed: false },
    })
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await user.click(screen.getByRole('button', { name: 'Usage Eligibility' }))
    await user.selectOptions(screen.getByLabelText('Source'), 'src-1')
    await user.click(screen.getByRole('button', { name: 'Check all uses at a glance' }))
    await waitFor(() => expect(document.querySelector('.metric-grid')).toBeInTheDocument())
    const grid = document.querySelector('.metric-grid')
    expect(within(grid).getByText('rag').nextSibling).toHaveTextContent('Allowed')
    expect(within(grid).getByText('training').nextSibling).toHaveTextContent('Blocked')
  })
})

describe('SourcesRightsPage: Blocked Items tab', () => {
  it('lists only restricted/rejected sources, not every source', async () => {
    mockList([SOURCE_DRAFT, SOURCE_REJECTED])
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('2'))
    await user.click(screen.getByRole('button', { name: 'Blocked Items' }))
    expect(screen.getByText('SRC-WEB-0001')).toBeInTheDocument()
    expect(screen.queryByText('SRC-HUMAN-0001')).not.toBeInTheDocument()
  })

  it('shows an honest empty state when nothing is blocked', async () => {
    mockList([SOURCE_DRAFT])
    const user = userEvent.setup()
    render(<SourcesRightsPage />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('1'))
    await user.click(screen.getByRole('button', { name: 'Blocked Items' }))
    expect(screen.getByText(/No restricted or rejected sources/)).toBeInTheDocument()
  })
})
