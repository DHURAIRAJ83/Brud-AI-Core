import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OverviewPage from './OverviewPage.jsx'

vi.mock('../services/api.js', () => ({
  getOverview: vi.fn(),
  miniBrainDefaultRetrievalProfile: vi.fn(),
  miniBrainWidgetHealth: vi.fn(),
  ragSpaces: vi.fn(),
  systemPilotMetrics: vi.fn(),
  systemRecentAudit: vi.fn(),
}))

const api = await import('../services/api.js')

const OVERVIEW_RESPONSE = { project: 'Brud AI', dataset_sources: 7, dataset_records: 120, training_jobs: 2, registered_models: 1 }
const SPACES_RESPONSE = { items: [{ public_id: 's1' }, { public_id: 's2' }] }
const METRICS_RESPONSE = {
  widget_plain_chat_count: 12, widget_grounded_chat_count: 9, grounded_chat_citation_render_count: 8,
  retrieval_profile_switch_count: 3, prompt_optimization_run_count: 4, gateway_export_run_count: 1,
}
const HEALTH_RESPONSE = { loaded: true, backend_type: 'local', current_model: 'test-model.gguf', available: true, error_message: null }
const DEFAULT_PROFILE_RESPONSE = { retrieval_profile_public_id: 'profile-1', name: 'Default profile' }
const AUDIT_RESPONSE = { items: [{ public_id: 'evt-1', event_type: 'dataset_uploaded', outcome: 'success', created_at: '2026-01-01T00:00:00Z' }] }

function mockDefaults() {
  api.getOverview.mockResolvedValue(OVERVIEW_RESPONSE)
  api.ragSpaces.mockResolvedValue(SPACES_RESPONSE)
  api.systemPilotMetrics.mockResolvedValue(METRICS_RESPONSE)
  api.miniBrainWidgetHealth.mockResolvedValue(HEALTH_RESPONSE)
  api.miniBrainDefaultRetrievalProfile.mockResolvedValue(DEFAULT_PROFILE_RESPONSE)
  api.systemRecentAudit.mockResolvedValue(AUDIT_RESPONSE)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('OverviewPage', () => {
  it('shows a loading state, then renders real KPI cards', async () => {
    mockDefaults()
    render(<OverviewPage onNavigate={vi.fn()} />)
    expect(screen.getAllByRole('status', { name: 'Loading' }).length).toBeGreaterThan(0)

    expect(await screen.findByText('Total Datasets')).toBeInTheDocument()
    expect(screen.getByText('Total Datasets').closest('article')).toHaveTextContent('7')
    expect(screen.getByText('Knowledge Spaces').closest('article')).toHaveTextContent('2')
    expect(screen.getByText('Total Chats').closest('article')).toHaveTextContent('12')
    expect(screen.getByText('Total Grounded Chats').closest('article')).toHaveTextContent('9')
    expect(screen.getByText('Total Prompt Runs').closest('article')).toHaveTextContent('4')
    expect(screen.getByText('Gateway Exports').closest('article')).toHaveTextContent('1')
    expect(screen.getByText('Runtime Health').closest('article')).toHaveTextContent('available')
    expect(screen.getByText('Active Retrieval Profile').closest('article')).toHaveTextContent('Default profile')
  })

  it('renders recent activity from real audit events', async () => {
    mockDefaults()
    render(<OverviewPage onNavigate={vi.fn()} />)
    expect(await screen.findByText(/dataset uploaded/)).toBeInTheDocument()
  })

  it('shows an empty state when there are no audit events', async () => {
    mockDefaults()
    api.systemRecentAudit.mockResolvedValue({ items: [] })
    render(<OverviewPage onNavigate={vi.fn()} />)
    expect(await screen.findByText('No audit events have been recorded yet.')).toBeInTheDocument()
  })

  it('shows a retry banner on failure and recovers on click', async () => {
    mockDefaults()
    api.getOverview.mockRejectedValueOnce(new Error('Network error.'))
    const user = userEvent.setup()
    render(<OverviewPage onNavigate={vi.fn()} />)
    expect(await screen.findByText('Network error.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByText('Total Datasets')).toBeInTheDocument())
  })

  it('quick actions navigate to the real target pages', async () => {
    mockDefaults()
    const onNavigate = vi.fn()
    const user = userEvent.setup()
    render(<OverviewPage onNavigate={onNavigate} />)
    await screen.findByText('Total Datasets')

    await user.click(screen.getByRole('button', { name: 'Upload Dataset' }))
    expect(onNavigate).toHaveBeenCalledWith('Data Workspace Wizard')

    await user.click(screen.getByRole('button', { name: 'Start Grounded Chat' }))
    expect(onNavigate).toHaveBeenCalledWith('Brud Mini Brain')

    await user.click(screen.getByRole('button', { name: 'Switch Profile' }))
    expect(onNavigate).toHaveBeenCalledWith('Knowledge & RAG')

    await user.click(screen.getByRole('button', { name: 'Open Pilot Metrics' }))
    expect(onNavigate).toHaveBeenCalledWith('Pilot Metrics')
  })

  it('shows "none set" when there is no active default retrieval profile', async () => {
    mockDefaults()
    api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: null, name: null })
    render(<OverviewPage onNavigate={vi.fn()} />)
    expect(await screen.findByText('none set')).toBeInTheDocument()
  })
})
