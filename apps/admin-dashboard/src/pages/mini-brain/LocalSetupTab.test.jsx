import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LocalSetupTab from './LocalSetupTab.jsx'

function baseProps(overrides = {}) {
  return {
    lcSubTab: 'Hardware',
    setLcSubTab: vi.fn(),
    lcHardwareData: null,
    lcSetupBusy: false,
    runLcScan: vi.fn(),
    lcScannedModels: [],
    selectLcScannedModel: vi.fn(),
    loadLcRecommendations: vi.fn(),
    lcRecommendationsData: null,
    lcLocalForm: { model_path: '', context_length: '', max_tokens: '', temperature: '', threads: '', additional_model_dirs: '' },
    setLcLocalForm: vi.fn(),
    saveLcLocalModel: vi.fn(),
    testLcLocalModel: vi.fn(),
    lcCatalog: [],
    lcProviderForm: vi.fn(() => ({ api_key: '', model: '', enabled: false })),
    updateLcProviderForm: vi.fn(),
    saveLcProvider: vi.fn(),
    lcDiag: null,
    loadLcGuide: vi.fn(),
    lcGuide: null,
    ...overrides,
  }
}

describe('LocalSetupTab', () => {
  it('renders all 8 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setLcSubTab = vi.fn()
    render(<LocalSetupTab {...baseProps({ setLcSubTab })} />)
    for (const label of ['Hardware', 'Local Models', 'Recommendations', 'Local Configuration', 'External Providers', 'Diagnostics', 'Setup Guide', 'Help']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Recommendations' }))
    expect(setLcSubTab).toHaveBeenCalledWith('Recommendations')
  })

  it('Hardware: shows a skeleton before loaded', () => {
    render(<LocalSetupTab {...baseProps()} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('Local Models: calls the real scan action', async () => {
    const user = userEvent.setup()
    const runLcScan = vi.fn()
    render(<LocalSetupTab {...baseProps({ lcSubTab: 'Local Models', runLcScan })} />)
    await user.click(screen.getByRole('button', { name: 'Scan for local models' }))
    expect(runLcScan).toHaveBeenCalled()
  })

  it('Local Configuration: real save button calls the handler', async () => {
    const user = userEvent.setup()
    const saveLcLocalModel = vi.fn()
    render(<LocalSetupTab {...baseProps({ lcSubTab: 'Local Configuration', saveLcLocalModel })} />)
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(saveLcLocalModel).toHaveBeenCalled()
  })

  it('External Providers: real save button calls the handler with the right provider key', async () => {
    const user = userEvent.setup()
    const saveLcProvider = vi.fn()
    render(<LocalSetupTab {...baseProps({
      lcSubTab: 'External Providers',
      lcCatalog: [{ provider_key: 'openai', context_window: 128000, reasoning_level: { en: 'high', ta: 'உயர்' }, cost_hint: { en: '$', ta: '$' }, recommended_models: ['gpt-4'] }],
      saveLcProvider,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(saveLcProvider).toHaveBeenCalledWith('openai')
  })

  it('Setup Guide: calls the real guide builder', async () => {
    const user = userEvent.setup()
    const loadLcGuide = vi.fn()
    render(<LocalSetupTab {...baseProps({ lcSubTab: 'Setup Guide', loadLcGuide })} />)
    await user.click(screen.getByRole('button', { name: 'Build setup guide' }))
    expect(loadLcGuide).toHaveBeenCalled()
  })
})
