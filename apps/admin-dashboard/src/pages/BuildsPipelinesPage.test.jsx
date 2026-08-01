import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BuildsPipelinesPage from './BuildsPipelinesPage.jsx'

vi.mock('../services/api.js', () => ({
  cancelGovernedBuild: vi.fn(), confirmGovernedBuild: vi.fn(), createGovernedBuild: vi.fn(),
  executeGovernedBuild: vi.fn(), generateGovernedBuildManifest: vi.fn(), governedBuild: vi.fn(),
  governedBuildBlockedItems: vi.fn(), governedBuildHistory: vi.fn(), governedBuildItems: vi.fn(),
  governedBuildManifest: vi.fn(), governedBuildSummary: vi.fn(), governedBuilds: vi.fn(),
  governedCommercialPreflight: vi.fn(), governedEvaluationHandoff: vi.fn(),
  governedPretrainingHandoff: vi.fn(), governedPublicExportPreflight: vi.fn(),
  governedRagHandoff: vi.fn(), governedSftHandoff: vi.fn(), governedTokenizerHandoff: vi.fn(),
  lineageForEntity: vi.fn(), preflightGovernedBuild: vi.fn(), previewGovernedBuild: vi.fn(),
  updateGovernedBuildSelection: vi.fn(),
}))

const api = await import('../services/api.js')

const BUILD = {
  public_id: 'gbr-1', build_code: 'GBR-0001', target_pipeline: 'rag', status: 'draft',
}

function mockBaseline() {
  api.governedBuildSummary.mockResolvedValue({ counts_by_status: { draft: 1 } })
  api.governedBuilds.mockResolvedValue({ items: [BUILD] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('BuildsPipelinesPage: navigation', () => {
  it('renders all eleven required tabs', async () => {
    mockBaseline()
    render(<BuildsPipelinesPage />)
    for (const tab of [
      'Overview', 'Create Build', 'Build Preview', 'Blocked Records', 'Dataset Versions',
      'RAG Handoffs', 'Tokenizer & Training', 'Evaluation Builds', 'Manifests', 'Lineage', 'History',
    ]) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview shows real build-status counts, including zero states', async () => {
    mockBaseline()
    render(<BuildsPipelinesPage />)
    await waitFor(() => expect(screen.getByText('draft').nextSibling).toHaveTextContent('1'))
    expect(screen.getByText('completed').nextSibling).toHaveTextContent('0')
  })
})

describe('BuildsPipelinesPage: create build', () => {
  it('creating a build calls createGovernedBuild with the selected target pipeline', async () => {
    mockBaseline()
    api.createGovernedBuild.mockResolvedValue(BUILD)
    api.governedBuild.mockResolvedValue({ ...BUILD, artifact_links: [] })
    const user = userEvent.setup()
    render(<BuildsPipelinesPage />)
    await user.click(screen.getByRole('button', { name: 'Create Build' }))
    await waitFor(() => screen.getByText('Step 1: choose a target pipeline'))
    await user.selectOptions(screen.getByRole('combobox'), 'rag')
    await user.click(screen.getByRole('button', { name: 'Create build request' }))
    await waitFor(() => expect(api.createGovernedBuild).toHaveBeenCalled())
    const call = api.createGovernedBuild.mock.calls[0][0]
    expect(call.target_pipeline).toBe('rag')
  })
})

describe('BuildsPipelinesPage: build preview lifecycle', () => {
  async function selectBuild(user) {
    mockBaseline()
    api.governedBuild.mockResolvedValue({ ...BUILD, artifact_links: [] })
    render(<BuildsPipelinesPage />)
    await user.click(screen.getByRole('button', { name: 'Build Preview' }))
    await waitFor(() => screen.getByText('Select a build request'))
    await user.selectOptions(screen.getByRole('combobox'), 'gbr-1')
    await waitFor(() => screen.getByText('GBR-0001'))
  }

  it('preview calls previewGovernedBuild for the selected build', async () => {
    api.previewGovernedBuild = vi.fn().mockResolvedValue({
      eligible_records: [], blocked_records: [], warning_records: [], excluded_records: [],
      source_summary: {}, rights_summary: {}, language_distribution: {}, record_type_distribution: {},
    })
    const user = userEvent.setup()
    await selectBuild(user)
    await user.click(screen.getByRole('button', { name: 'Preview (ephemeral)' }))
    await waitFor(() => expect(api.previewGovernedBuild).toHaveBeenCalledWith('gbr-1'))
  })

  it('preflight calls preflightGovernedBuild for the selected build', async () => {
    api.preflightGovernedBuild.mockResolvedValue({ ...BUILD, status: 'preflight_ready' })
    const user = userEvent.setup()
    await selectBuild(user)
    await user.click(screen.getByRole('button', { name: 'Run preflight' }))
    await waitFor(() => expect(api.preflightGovernedBuild).toHaveBeenCalledWith('gbr-1'))
  })

  it('confirm is disabled until the build is preflight_ready', async () => {
    const user = userEvent.setup()
    await selectBuild(user)
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
  })
})

describe('BuildsPipelinesPage: blocked records', () => {
  it('loads blocked items for the selected build', async () => {
    mockBaseline()
    api.governedBuild.mockResolvedValue({ ...BUILD, artifact_links: [] })
    api.governedBuildBlockedItems.mockResolvedValue({
      items: [{ public_id: 'item-1', entity_public_id: 'rec-1', decision_code: 'LEGACY_UNCLASSIFIED', blocking_reasons: ['not yet classified'] }],
    })
    const user = userEvent.setup()
    render(<BuildsPipelinesPage />)
    await user.click(screen.getByRole('button', { name: 'Build Preview' }))
    await user.selectOptions(screen.getByRole('combobox'), 'gbr-1')
    await waitFor(() => screen.getByText('GBR-0001'))
    await user.click(screen.getByRole('button', { name: 'Blocked Records' }))
    await user.click(screen.getByRole('button', { name: 'Load blocked records' }))
    await waitFor(() => screen.getByText('rec-1'))
    expect(screen.getByText('LEGACY_UNCLASSIFIED')).toBeInTheDocument()
  })
})

describe('BuildsPipelinesPage: lineage', () => {
  it('tracing lineage calls lineageForEntity with the entered entity id', async () => {
    mockBaseline()
    api.lineageForEntity.mockResolvedValue({ complete: true, nodes: [], edges: [] })
    const user = userEvent.setup()
    render(<BuildsPipelinesPage />)
    await user.click(screen.getByRole('button', { name: 'Lineage' }))
    await waitFor(() => screen.getByPlaceholderText('dataset_record public id'))
    await user.type(screen.getByPlaceholderText('dataset_record public id'), 'ds-1')
    await user.click(screen.getByRole('button', { name: 'Trace' }))
    await waitFor(() => expect(api.lineageForEntity).toHaveBeenCalledWith('dataset_record', 'ds-1'))
  })
})
