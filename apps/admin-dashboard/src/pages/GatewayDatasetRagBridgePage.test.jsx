import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GatewayDatasetRagBridgePage from './GatewayDatasetRagBridgePage.jsx'

vi.mock('../services/api.js', () => ({
  egdbExportToDataset: vi.fn(),
  gaProviderRuns: vi.fn(),
  gaSessions: vi.fn(),
  ragSpaces: vi.fn(),
  systemRecentAudit: vi.fn(),
}))

const api = await import('../services/api.js')

const SESSIONS_RESPONSE = {
  items: [
    { public_id: 'sess-accepted', topic: 'Tamil idiom coverage', purpose: 'data_acquisition_assistance', status: 'admin_accepted', requested_provider_keys: ['openai'] },
    { public_id: 'sess-pending', topic: 'Still reviewing', purpose: 'data_acquisition_assistance', status: 'in_progress', requested_provider_keys: ['anthropic'] },
  ],
}

const SPACES_RESPONSE = { items: [{ public_id: 'space-1', name: 'General Knowledge' }] }
const PROVIDER_RUNS_RESPONSE = { items: [{ public_id: 'run-1', status: 'success' }] }
const AUDIT_RESPONSE = {
  items: [
    { public_id: 'evt-1', event_type: 'external_gateway_dataset_export_started', outcome: 'success', resource_type: 'external_gateway_dataset_bridge', resource_public_id: 'sess-accepted', created_at: '2026-01-01T00:00:00Z' },
    { public_id: 'evt-2', event_type: 'external_gateway_dataset_export_completed', outcome: 'success', resource_type: 'external_gateway_dataset_bridge', resource_public_id: 'sess-accepted', created_at: '2026-01-01T00:00:05Z' },
    { public_id: 'evt-3', event_type: 'unrelated_event', outcome: 'success', resource_type: 'some_other_resource', resource_public_id: 'sess-accepted', created_at: '2026-01-01T00:00:06Z' },
  ],
}

const EXPORT_RESULT = {
  session_public_id: 'sess-accepted',
  dataset_source_public_id: 'source-1',
  created_record_public_ids: ['rec-1', 'rec-2'],
  duplicate_provider_run_public_ids: [],
  skipped_provider_run_public_ids: [],
  rag_source_public_ids: ['rag-src-1'],
  ingest_to_rag: true,
  source_version_public_ids: ['ver-1'],
  chunk_set_public_ids: ['cs-1'],
  embedding_run_public_ids: ['er-1'],
  vector_index_public_ids: ['vi-1'],
  retrieval_profile_public_id: 'profile-1',
}

function mockDefaults() {
  api.gaSessions.mockResolvedValue(SESSIONS_RESPONSE)
  api.ragSpaces.mockResolvedValue(SPACES_RESPONSE)
  api.gaProviderRuns.mockResolvedValue(PROVIDER_RUNS_RESPONSE)
  api.systemRecentAudit.mockResolvedValue(AUDIT_RESPONSE)
  api.egdbExportToDataset.mockResolvedValue(EXPORT_RESULT)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('GatewayDatasetRagBridgePage', () => {
  it('lists only admin_accepted sessions, not pending ones', async () => {
    mockDefaults()
    render(<GatewayDatasetRagBridgePage />)
    expect(await screen.findByText('Tamil idiom coverage')).toBeInTheDocument()
    expect(screen.queryByText('Still reviewing')).not.toBeInTheDocument()
  })

  it('selecting a session loads its provider runs and audit events, filtered to this bridge', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<GatewayDatasetRagBridgePage />)
    await user.click(await screen.findByText('Tamil idiom coverage'))
    await waitFor(() => expect(api.gaProviderRuns).toHaveBeenCalledWith('sess-accepted'))
    expect(await screen.findByText(/1 provider run\(s\) collected/)).toBeInTheDocument()
    expect(await screen.findByText('external_gateway_dataset_export_started')).toBeInTheDocument()
    expect(await screen.findByText('external_gateway_dataset_export_completed')).toBeInTheDocument()
    // The unrelated resource_type event must be filtered out client-side.
    expect(screen.queryByText('unrelated_event')).not.toBeInTheDocument()
  })

  it('requires a RAG knowledge space before allowing export when the RAG checkbox is on', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<GatewayDatasetRagBridgePage />)
    await user.click(await screen.findByText('Tamil idiom coverage'))
    await user.click(await screen.findByLabelText('Also ingest into RAG'))
    expect(await screen.findByRole('button', { name: 'Run export' })).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('RAG knowledge space'), 'space-1')
    expect(screen.getByRole('button', { name: 'Run export' })).toBeEnabled()
  })

  it('runs the export and renders real status counts from the response', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<GatewayDatasetRagBridgePage />)
    await user.click(await screen.findByText('Tamil idiom coverage'))
    await user.click(await screen.findByLabelText('Also ingest into RAG'))
    await user.selectOptions(screen.getByLabelText('RAG knowledge space'), 'space-1')
    await user.click(screen.getByRole('button', { name: 'Run export' }))
    await waitFor(() => expect(api.egdbExportToDataset).toHaveBeenCalledWith('sess-accepted', expect.objectContaining({
      ingest_to_rag: true, rag_knowledge_space_public_id: 'space-1',
    })))
    const recordsCard = await screen.findByText('Records created')
    expect(recordsCard.closest('article')).toHaveTextContent('2')
    const ragCard = await screen.findByText('RAG sources created')
    expect(ragCard.closest('article')).toHaveTextContent('1')
    expect(await screen.findByText(/Retrieval profile created: profile-1/)).toBeInTheDocument()
  })

  it('shows a generic error notice when the export call fails', async () => {
    mockDefaults()
    api.egdbExportToDataset.mockRejectedValue(new Error('session status is not admin_accepted'))
    const user = userEvent.setup()
    render(<GatewayDatasetRagBridgePage />)
    await user.click(await screen.findByText('Tamil idiom coverage'))
    await user.click(screen.getByRole('button', { name: 'Run export' }))
    expect(await screen.findByText('session status is not admin_accepted')).toBeInTheDocument()
  })

  it('shows an empty-state message when there are no accepted sessions', async () => {
    mockDefaults()
    api.gaSessions.mockResolvedValue({ items: [] })
    render(<GatewayDatasetRagBridgePage />)
    expect(await screen.findByText(/No sessions with an admin-accepted decision yet/)).toBeInTheDocument()
  })

  it('shows a retry button on load failure and recovers on click', async () => {
    mockDefaults()
    api.gaSessions.mockRejectedValueOnce(new Error('Network error.'))
    const user = userEvent.setup()
    render(<GatewayDatasetRagBridgePage />)
    expect(await screen.findByText('Network error.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByText('Tamil idiom coverage')).toBeInTheDocument())
  })
})
