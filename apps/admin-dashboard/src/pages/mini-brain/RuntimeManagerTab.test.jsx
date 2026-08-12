import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RuntimeManagerTab from './RuntimeManagerTab.jsx'

function baseProps(overrides = {}) {
  return {
    rmStatusData: null,
    rmHardwareData: null,
    rmSubTab: 'Overview',
    setRmSubTab: vi.fn(),
    rmBusy: false,
    installRecommendedModel: vi.fn(),
    rmCatalogData: [],
    setRmSelectedModelId: vi.fn(),
    rmInstalledList: [],
    runRmRemove: vi.fn(),
    rmSelectedModelId: '',
    runRmDownload: vi.fn(),
    runRmVerify: vi.fn(),
    runRmInstallSelected: vi.fn(),
    rmLastActionResult: null,
    rmLoadForm: { context_length: '', max_tokens: '', temperature: '', threads: '' },
    setRmLoadForm: vi.fn(),
    runRmLoad: vi.fn(),
    runRmUnload: vi.fn(),
    rmBenchmarkPrompt: '',
    setRmBenchmarkPrompt: vi.fn(),
    runRmBenchmark: vi.fn(),
    rmLastBenchmarkResult: null,
    loadRmEvents: vi.fn(),
    rmEventsList: [],
    loadRmHistory: vi.fn(),
    rmMemoryList: [],
    ...overrides,
  }
}

describe('RuntimeManagerTab', () => {
  it('renders all 10 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setRmSubTab = vi.fn()
    render(<RuntimeManagerTab {...baseProps({ setRmSubTab })} />)
    for (const label of ['Overview', 'Catalog', 'Installed', 'Download', 'Load / Unload', 'Benchmark', 'Performance', 'Diagnostics', 'Events', 'History']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Benchmark' }))
    expect(setRmSubTab).toHaveBeenCalledWith('Benchmark')
  })

  it('Overview: calls the real install-recommended action', async () => {
    const user = userEvent.setup()
    const installRecommendedModel = vi.fn()
    render(<RuntimeManagerTab {...baseProps({ installRecommendedModel })} />)
    await user.click(screen.getByRole('button', { name: /Install Recommended Model/ }))
    expect(installRecommendedModel).toHaveBeenCalled()
  })

  it('Installed: real remove button calls the handler with the right model name', async () => {
    const user = userEvent.setup()
    const runRmRemove = vi.fn()
    render(<RuntimeManagerTab {...baseProps({
      rmSubTab: 'Installed',
      rmInstalledList: [{ public_id: 'm-1', model_name: 'qwen2.5-0.5b', status: 'installed', file_size_bytes: 500000000 }],
      runRmRemove,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    expect(runRmRemove).toHaveBeenCalledWith('qwen2.5-0.5b')
  })

  it('Download: real download button calls the handler when a model is selected', async () => {
    const user = userEvent.setup()
    const runRmDownload = vi.fn()
    render(<RuntimeManagerTab {...baseProps({ rmSubTab: 'Download', rmSelectedModelId: 'qwen2.5-0.5b', runRmDownload })} />)
    const card = screen.getByPlaceholderText('e.g. qwen2.5-1.5b-instruct-q4_k_m').closest('.card')
    await user.click(within(card).getByRole('button', { name: 'Download' }))
    expect(runRmDownload).toHaveBeenCalled()
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<RuntimeManagerTab {...baseProps({ rmSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
