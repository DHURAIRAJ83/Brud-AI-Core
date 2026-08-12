import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PilotMetricsPage from './PilotMetricsPage.jsx'

vi.mock('../services/api.js', () => ({
  systemPilotMetrics: vi.fn(),
}))

const api = await import('../services/api.js')

const COUNTS_RESPONSE = {
  widget_plain_chat_count: 3,
  widget_grounded_chat_count: 5,
  grounded_chat_citation_render_count: 4,
  retrieval_profile_switch_count: 1,
  prompt_optimization_run_count: 2,
  gateway_export_run_count: 0,
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('PilotMetricsPage', () => {
  it('shows a loading state, then renders real aggregated counts', async () => {
    api.systemPilotMetrics.mockResolvedValue(COUNTS_RESPONSE)
    render(<PilotMetricsPage />)
    expect(screen.getByText(/Loading pilot metrics/)).toBeInTheDocument()

    expect(await screen.findByText('Widget grounded chats sent')).toBeInTheDocument()
    expect(screen.getByText('Widget grounded chats sent').closest('article')).toHaveTextContent('5')
    expect(screen.getByText('Prompt optimization runs').closest('article')).toHaveTextContent('2')
    expect(screen.getByText('Gateway dataset exports').closest('article')).toHaveTextContent('0')
  })

  it('shows an empty-state message when every count is zero', async () => {
    api.systemPilotMetrics.mockResolvedValue({
      widget_plain_chat_count: 0, widget_grounded_chat_count: 0, grounded_chat_citation_render_count: 0,
      retrieval_profile_switch_count: 0, prompt_optimization_run_count: 0, gateway_export_run_count: 0,
    })
    render(<PilotMetricsPage />)
    expect(await screen.findByText(/No pilot usage has been recorded yet/)).toBeInTheDocument()
  })

  it('shows a retry button on failure and recovers on click', async () => {
    api.systemPilotMetrics.mockRejectedValueOnce(new Error('Network error.'))
    api.systemPilotMetrics.mockResolvedValueOnce(COUNTS_RESPONSE)
    const user = userEvent.setup()
    render(<PilotMetricsPage />)
    expect(await screen.findByText('Network error.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByText('Widget grounded chats sent')).toBeInTheDocument())
  })
})
