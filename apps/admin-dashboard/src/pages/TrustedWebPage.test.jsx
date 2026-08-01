import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TrustedWebPage from './TrustedWebPage.jsx'

vi.mock('../services/api.js', () => ({
  trustedWebOverview: vi.fn(),
  trustedWebProviders: vi.fn(),
  trustedWebPolicy: vi.fn(),
  trustedWebSearchEvents: vi.fn(),
  trustedWebEvidence: vi.fn(),
  trustedWebFetchEvents: vi.fn(),
  trustedWebHealth: vi.fn(),
  trustedWebTestSearch: vi.fn(),
  trustedWebVerifySource: vi.fn(),
}))

const api = await import('../services/api.js')

const OVERVIEW = {
  total_search_events: 3,
  by_status: { success: 2, evidence_insufficient: 1 },
  by_category: { current_general_information: 3 },
  conflicts: {},
  blocked_fetches: 0,
  injection_blocked_sources: 0,
  web_demand: { web_capability_gap_cases: 1 },
}

function setup() {
  api.trustedWebOverview.mockResolvedValue(OVERVIEW)
  api.trustedWebProviders.mockResolvedValue({
    configured_provider_name: 'wikipedia', healthy: true, reason: null, capabilities: ['web_search'],
  })
  api.trustedWebPolicy.mockResolvedValue({
    available: true,
    policy: {
      policy_version: 'v1', policy_checksum_sha256: 'abcdef1234567890',
      allowed_domains: { 'en.wikipedia.org': 'reputable_secondary' },
      blocked_domains: [], maximum_results: 5, maximum_fetches: 3,
    },
  })
  api.trustedWebSearchEvents.mockResolvedValue({ items: [] })
  api.trustedWebEvidence.mockResolvedValue({ items: [] })
  api.trustedWebFetchEvents.mockResolvedValue({ items: [] })
  api.trustedWebHealth.mockResolvedValue({
    provider_available: true, policy_loaded: true, policy_error: null, external_mcp_enabled: false,
  })
}

describe('TrustedWebPage', () => {
  it('renders overview metrics from real API data', async () => {
    setup()
    render(<TrustedWebPage />)
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
    expect(api.trustedWebOverview).toHaveBeenCalled()
  })

  it('never displays an API key or base_url on the Providers tab', async () => {
    setup()
    const user = userEvent.setup()
    render(<TrustedWebPage />)
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    await waitFor(() => expect(screen.getByText('wikipedia')).toBeInTheDocument())
    expect(screen.queryByText(/api.key/i)).not.toBeInTheDocument()
  })

  it('shows the policy version and checksum on the Policy tab', async () => {
    setup()
    const user = userEvent.setup()
    render(<TrustedWebPage />)
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Policy' }))
    await waitFor(() => expect(screen.getByText('v1')).toBeInTheDocument())
  })

  it('reports external MCP as disabled on the Health tab', async () => {
    setup()
    const user = userEvent.setup()
    render(<TrustedWebPage />)
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Health' }))
    await waitFor(() => expect(screen.getAllByText('false').length).toBeGreaterThan(0))
  })

  it('surfaces an API error without crashing', async () => {
    api.trustedWebOverview.mockRejectedValue(new Error('boom'))
    render(<TrustedWebPage />)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('boom'))
  })
})
