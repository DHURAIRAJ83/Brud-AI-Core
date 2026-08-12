import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProviderSettingsTab from './ProviderSettingsTab.jsx'

function baseProps(overrides = {}) {
  return {
    psSubTab: 'Overview',
    setPsSubTab: vi.fn(),
    psDiag: null,
    renderPsProviderCard: vi.fn((key) => <div key={key}>card-for-{key}</div>),
    psTestResults: {},
    psAuditList: [],
    ...overrides,
  }
}

describe('ProviderSettingsTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setPsSubTab = vi.fn()
    render(<ProviderSettingsTab {...baseProps({ setPsSubTab })} />)
    for (const label of ['Overview', 'External AI', 'OpenAI', 'Anthropic', 'Gemini', 'OpenRouter', 'Speech', 'STT', 'TTS', 'Local Models', 'Connection Tests', 'Audit', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Anthropic' }))
    expect(setPsSubTab).toHaveBeenCalledWith('Anthropic')
  })

  it('External AI: renders all 4 real provider cards', () => {
    const renderPsProviderCard = vi.fn((key) => <div key={key}>card-for-{key}</div>)
    render(<ProviderSettingsTab {...baseProps({ psSubTab: 'External AI', renderPsProviderCard })} />)
    expect(renderPsProviderCard).toHaveBeenCalledWith('openrouter')
    expect(renderPsProviderCard).toHaveBeenCalledWith('openai')
    expect(renderPsProviderCard).toHaveBeenCalledWith('anthropic')
    expect(renderPsProviderCard).toHaveBeenCalledWith('gemini')
    expect(screen.getByText('card-for-openai')).toBeInTheDocument()
  })

  it('OpenAI: renders the real single provider card', () => {
    const renderPsProviderCard = vi.fn((key) => <div key={key}>card-for-{key}</div>)
    render(<ProviderSettingsTab {...baseProps({ psSubTab: 'OpenAI', renderPsProviderCard })} />)
    expect(renderPsProviderCard).toHaveBeenCalledWith('openai')
    expect(screen.getByText('card-for-openai')).toBeInTheDocument()
  })

  it('Connection Tests: shows a real recorded test result', () => {
    render(<ProviderSettingsTab {...baseProps({
      psSubTab: 'Connection Tests',
      psTestResults: { 'prov-1': { provider_key: 'openai', status: 'success', latency_ms: 120 } },
    })} />)
    expect(screen.getByText(/openai -- success -- 120ms/)).toBeInTheDocument()
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<ProviderSettingsTab {...baseProps({ psSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
