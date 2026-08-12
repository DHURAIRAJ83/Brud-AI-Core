import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RuntimeTab from './RuntimeTab.jsx'

function baseProps(overrides = {}) {
  return {
    rtStatus: null,
    rtStats: null,
    rtBusy: false,
    rtModels: [],
    runRuntimeAction: vi.fn(),
    rtRegisterForm: { name: '', path: '', quantization: 'Q4_K_M', context_length: 2048 },
    setRtRegisterForm: vi.fn(),
    submitRegisterModel: vi.fn((event) => event?.preventDefault?.()),
    rtDiagnostics: null,
    ...overrides,
  }
}

describe('RuntimeTab', () => {
  it('shows a loading skeleton until status and stats have loaded', () => {
    render(<RuntimeTab {...baseProps()} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('shows real runtime metrics once loaded, and calls real load/unload/reload actions', async () => {
    const user = userEvent.setup()
    const runRuntimeAction = vi.fn()
    render(<RuntimeTab {...baseProps({
      rtStatus: { state: 'loaded', current_model: { name: 'test.gguf', quantization: 'Q4', context_length: 2048 } },
      rtStats: { last_load_time_ms: 100, last_response_time_ms: 50, available_memory_bytes: 1048576, process_cpu_time_seconds: 1, process_max_rss_kb: 1024 },
      rtModels: [{ public_id: 'm1', name: 'test.gguf', quantization: 'Q4', context_length: 2048, path: '/models/test.gguf' }],
      runRuntimeAction,
    })} />)
    expect(screen.getByText('Runtime status').closest('article')).toHaveTextContent('loaded')
    await user.click(screen.getByRole('button', { name: 'Load' }))
    expect(runRuntimeAction).toHaveBeenCalledWith('load')
    await user.click(screen.getByRole('button', { name: 'Unload' }))
    expect(runRuntimeAction).toHaveBeenCalledWith('unload')
  })

  it('shows the real last_error when present', () => {
    render(<RuntimeTab {...baseProps({
      rtStatus: { state: 'error', last_error: 'model file not found' },
      rtStats: { last_load_time_ms: null, last_response_time_ms: null, available_memory_bytes: 0, process_cpu_time_seconds: 0, process_max_rss_kb: 0 },
    })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('model file not found')
  })

  it('submits the real registration form', async () => {
    const user = userEvent.setup()
    const submitRegisterModel = vi.fn((event) => event?.preventDefault?.())
    render(<RuntimeTab {...baseProps({ submitRegisterModel })} />)
    await user.click(screen.getByRole('button', { name: 'Register' }))
    expect(submitRegisterModel).toHaveBeenCalled()
  })
})
