import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DeterministicToolsPage from './DeterministicToolsPage.jsx'

vi.mock('../services/api.js', () => ({
  toolsOverview: vi.fn(),
  toolsRegistry: vi.fn(),
  toolsExecutionEvents: vi.fn(),
  toolsTest: vi.fn(),
}))

const api = await import('../services/api.js')

const REGISTRY = [
  {
    tool_name: 'calculator', tool_version: 'v1', risk_level: 'low', source: 'built_in_deterministic',
    permission: 'public_safe_deterministic', public_enabled: true, admin_enabled: true,
    timeout_seconds: 2.0, maximum_input_size: 200,
  },
  {
    tool_name: 'unit_conversion', tool_version: 'v1', risk_level: 'low', source: 'built_in_deterministic',
    permission: 'public_safe_deterministic', public_enabled: true, admin_enabled: true,
    timeout_seconds: 2.0, maximum_input_size: 40,
  },
  {
    tool_name: 'date_time_arithmetic', tool_version: 'v1', risk_level: 'low', source: 'built_in_deterministic',
    permission: 'public_safe_deterministic', public_enabled: true, admin_enabled: true,
    timeout_seconds: 2.0, maximum_input_size: 40,
  },
]

function setup() {
  api.toolsOverview.mockResolvedValue({
    total_executions: 5, by_tool: { calculator: 5 }, by_status: { success: 5 },
    external_mcp_enabled: false,
  })
  api.toolsRegistry.mockResolvedValue({ tools: REGISTRY })
  api.toolsExecutionEvents.mockResolvedValue({ items: [] })
}

describe('DeterministicToolsPage', () => {
  it('renders overview metrics from real API data', async () => {
    setup()
    render(<DeterministicToolsPage />)
    await waitFor(() => expect(screen.getByText('Total executions')).toBeInTheDocument())
    expect(api.toolsOverview).toHaveBeenCalled()
  })

  it('lists exactly the three built-in tools on the Registry tab', async () => {
    setup()
    const user = userEvent.setup()
    render(<DeterministicToolsPage />)
    await waitFor(() => expect(screen.getByText('Total executions')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Registry' }))
    await waitFor(() => expect(screen.getByText('calculator')).toBeInTheDocument())
    expect(screen.getByText('unit_conversion')).toBeInTheDocument()
    expect(screen.getByText('date_time_arithmetic')).toBeInTheDocument()
  })

  it('reports external MCP as disabled on the MCP Readiness tab', async () => {
    setup()
    const user = userEvent.setup()
    render(<DeterministicToolsPage />)
    await waitFor(() => expect(screen.getByText('Total executions')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'MCP Readiness' }))
    await waitFor(() => expect(screen.getByText('false')).toBeInTheDocument())
  })

  it('runs a calculator test via the Admin-only test endpoint', async () => {
    setup()
    api.toolsTest.mockResolvedValue({
      tool_name: 'calculator', tool_version: 'v1', status: 'success',
      output_payload: { result: '12193459430' }, error_code: null, latency_ms: 1,
    })
    const user = userEvent.setup()
    render(<DeterministicToolsPage />)
    await waitFor(() => expect(screen.getByText('Total executions')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Calculator' }))
    await user.click(screen.getByRole('button', { name: 'Run test' }))
    await waitFor(() => expect(api.toolsTest).toHaveBeenCalledWith(
      expect.objectContaining({ tool_name: 'calculator' })
    ))
  })

  it('surfaces an API error without crashing', async () => {
    api.toolsOverview.mockRejectedValue(new Error('boom'))
    render(<DeterministicToolsPage />)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('boom'))
  })
})
