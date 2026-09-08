import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AssistantSettingsPane from './AssistantSettingsPane.jsx'
import * as api from '../../services/api.js'

vi.mock('../../services/api.js', () => ({
  psProviders: vi.fn(),
  psDiagnostics: vi.fn(),
  psCreateProvider: vi.fn(),
  psEnableProvider: vi.fn(),
  psDisableProvider: vi.fn(),
  psSetSecret: vi.fn(),
  psDeleteSecret: vi.fn(),
  psTestConnection: vi.fn(),
}))

describe('AssistantSettingsPane', () => {
  const toast = { success: vi.fn(), error: vi.fn() }
  const onNavigate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    api.psProviders.mockResolvedValue({
      items: [
        {
          public_id: 'prov-openrouter',
          provider_key: 'openrouter',
          enabled: true,
          health: 'healthy',
          secrets: [{ secret_name: 'api_key', is_set: true, masked_indicator: 'sk-****' }],
        },
      ],
    })
    api.psDiagnostics.mockResolvedValue({
      encryption_available: true,
      configured_provider_count: 1,
      enabled_provider_count: 1,
      unavailable_providers: [],
    })
  })

  it('renders provider list and diagnostic cards', async () => {
    render(<AssistantSettingsPane toast={toast} onNavigate={onNavigate} />)
    await waitFor(() => {
      expect(screen.getByText('Assistant & Provider Settings')).toBeInTheDocument()
      expect(screen.getByText('OpenRouter')).toBeInTheDocument()
      expect(screen.getByText('Active (Fernet)')).toBeInTheDocument()
      expect(screen.getByText('Encrypted & Masked (sk-****)')).toBeInTheDocument()
    })
  })

  it('allows saving an encrypted API key and clears plaintext input', async () => {
    api.psSetSecret.mockResolvedValue({ ok: true })
    render(<AssistantSettingsPane toast={toast} onNavigate={onNavigate} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter API key (stored encrypted)')).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText('Enter API key (stored encrypted)')
    fireEvent.change(input, { target: { value: 'sk-my-super-secret-key' } })
    const saveBtn = screen.getByRole('button', { name: 'Save Key' })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(api.psSetSecret).toHaveBeenCalledWith('prov-openrouter', 'api_key', 'sk-my-super-secret-key')
      expect(toast.success).toHaveBeenCalledWith('API key encrypted and saved securely.')
      expect(input.value).toBe('') // Plaintext cleared
    })
  })

  it('runs connection test and displays latency', async () => {
    api.psTestConnection.mockResolvedValue({
      status: 'healthy',
      latency_ms: 120,
    })
    render(<AssistantSettingsPane toast={toast} onNavigate={onNavigate} />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Test Connection' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(api.psTestConnection).toHaveBeenCalledWith('prov-openrouter', 'api_key')
      expect(toast.success).toHaveBeenCalledWith('Connection successful (120ms)')
      expect(screen.getByText(/healthy \(120ms\)/i)).toBeInTheDocument()
    })
  })
})
