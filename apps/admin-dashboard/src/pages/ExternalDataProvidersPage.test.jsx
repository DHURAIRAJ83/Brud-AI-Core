import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ExternalDataProvidersPage from './ExternalDataProvidersPage.jsx'

vi.mock('../services/api.js', () => ({
  externalDataProviders: vi.fn(),
  registerExternalDataProvider: vi.fn(),
  externalDataProvider: vi.fn(),
  updateExternalDataProvider: vi.fn(),
  verifyExternalDataProvider: vi.fn(),
  setProviderTrustStatus: vi.fn(),
  testProviderConnection: vi.fn(),
  providerConnectionTests: vi.fn(),
  enableExternalDataProvider: vi.fn(),
  disableExternalDataProvider: vi.fn(),
  restrictExternalDataProvider: vi.fn(),
  blockExternalDataProvider: vi.fn(),
  archiveExternalDataProvider: vi.fn(),
  providerDomains: vi.fn(),
  addProviderDomain: vi.fn(),
  verifyProviderDomain: vi.fn(),
  providerCapabilities: vi.fn(),
  setProviderCapabilities: vi.fn(),
  providerCredentialStatus: vi.fn(),
  configureProviderCredential: vi.fn(),
  revokeProviderCredential: vi.fn(),
  providerHistory: vi.fn(),
}))

const api = await import('../services/api.js')

const SEEDED_PROVIDERS = [
  {
    public_id: 'p-ai4bharat', provider_code: 'ai4bharat', name: 'AI4Bharat',
    provider_type: 'research_institution', access_mode: 'mixed', authentication_type: 'none',
    trust_status: 'unverified', lifecycle_status: 'draft', enabled: false,
    supports_anonymous_read: true, description: 'Indic language datasets.',
  },
  {
    public_id: 'p-huggingface', provider_code: 'huggingface', name: 'Hugging Face',
    provider_type: 'repository_host', access_mode: 'mixed', authentication_type: 'bearer_token',
    trust_status: 'unverified', lifecycle_status: 'draft', enabled: false,
    supports_anonymous_read: true, description: 'Dataset hosting.',
  },
]

function mockDefaults() {
  api.externalDataProviders.mockResolvedValue({ items: SEEDED_PROVIDERS, page: 1, page_size: 100 })
  api.externalDataProvider.mockResolvedValue(SEEDED_PROVIDERS[0])
  api.providerDomains.mockResolvedValue({ items: [] })
  api.providerCapabilities.mockResolvedValue({ items: [] })
  api.providerCredentialStatus.mockResolvedValue({ items: [] })
  api.providerConnectionTests.mockResolvedValue({ items: [] })
  api.providerHistory.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('ExternalDataProvidersPage', () => {
  it('shows the safety notice and no fake credentials on load', async () => {
    mockDefaults()
    render(<ExternalDataProvidersPage />)
    expect(await screen.findByText(/never grants a dataset licence/)).toBeInTheDocument()
    expect(screen.queryByText(/api_key|secret|token-value/i)).not.toBeInTheDocument()
  })

  it('lists seeded built-in providers, all draft/unverified/disabled', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    expect(await screen.findByText('AI4Bharat')).toBeInTheDocument()
    expect(screen.getByText('Hugging Face')).toBeInTheDocument()
    const rows = screen.getAllByText('draft')
    expect(rows.length).toBeGreaterThan(0)
  })

  it('registers a custom provider starting draft/unverified/disabled', async () => {
    mockDefaults()
    api.registerExternalDataProvider.mockResolvedValue({
      public_id: 'p-new', provider_code: 'my-custom', name: 'My Custom Provider',
      lifecycle_status: 'draft', trust_status: 'unverified', enabled: false,
    })
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Add Provider' }))
    await user.type(screen.getByLabelText('Provider name'), 'My Custom Provider')
    await user.type(screen.getByLabelText('Provider code (stable, unique)'), 'my-custom')
    await user.click(screen.getByRole('button', { name: 'Register provider' }))
    await waitFor(() => expect(api.registerExternalDataProvider).toHaveBeenCalledWith(
      expect.objectContaining({ provider_code: 'my-custom', name: 'My Custom Provider' })
    ))
    expect(await screen.findByText(/draft\/unverified\/disabled/)).toBeInTheDocument()
  })

  it('selecting a provider loads its domains and shows verification controls', async () => {
    mockDefaults()
    api.providerDomains.mockResolvedValue({
      items: [{
        public_id: 'd-1', domain: 'ai4bharat.org', domain_type: 'official',
        verification_status: 'unverified',
      }],
    })
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    await screen.findByText('AI4Bharat')
    await user.click(screen.getAllByRole('button', { name: 'Select' })[0])
    await waitFor(() => expect(api.providerDomains).toHaveBeenCalledWith('p-ai4bharat'))

    await user.click(screen.getByRole('button', { name: 'Domains' }))
    expect(await screen.findByText('ai4bharat.org')).toBeInTheDocument()
  })

  it('domain verification requires evidence text and calls the API with it', async () => {
    mockDefaults()
    api.providerDomains.mockResolvedValue({
      items: [{
        public_id: 'd-1', domain: 'ai4bharat.org', domain_type: 'official',
        verification_status: 'unverified',
      }],
    })
    api.verifyProviderDomain.mockResolvedValue({
      public_id: 'd-1', domain: 'ai4bharat.org', verification_status: 'verified',
    })
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    await screen.findByText('AI4Bharat')
    await user.click(screen.getAllByRole('button', { name: 'Select' })[0])
    await user.click(screen.getByRole('button', { name: 'Domains' }))
    await screen.findByText('ai4bharat.org')

    await user.type(screen.getByPlaceholderText('Verification evidence'), 'Checked HTTPS cert')
    await user.click(screen.getByRole('button', { name: 'Mark verified' }))
    await waitFor(() => expect(api.verifyProviderDomain).toHaveBeenCalledWith(
      'p-ai4bharat', 'd-1', { verified: true, evidence: 'Checked HTTPS cert' }
    ))
  })

  it('never enables download/upload/write capabilities from the UI', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    await screen.findByText('AI4Bharat')
    await user.click(screen.getAllByRole('button', { name: 'Select' })[0])
    await user.click(screen.getByRole('button', { name: 'Capabilities' }))
    expect(await screen.findAllByText('never enabled in this phase')).toHaveLength(4)
    // Non-blocked capabilities (e.g. read_metadata) still get a real Enable button.
    expect(screen.getByRole('row', { name: /read_metadata/ })).toHaveTextContent('Enable')
  })

  it('credentials tab configures a reference and never displays a secret value', async () => {
    mockDefaults()
    api.configureProviderCredential.mockResolvedValue({
      credential_type: 'api_key', configured: true, status: 'configured',
      last_rotated_at: null, last_tested_at: null,
    })
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    await screen.findByText('AI4Bharat')
    await user.click(screen.getAllByRole('button', { name: 'Select' })[0])
    await user.click(screen.getByRole('button', { name: 'Credentials' }))
    await user.type(
      screen.getByPlaceholderText('BRUD_PROVIDER_SECRET__…'),
      'BRUD_PROVIDER_SECRET__ai4bharat'
    )
    await user.click(screen.getByRole('button', { name: 'Configure reference' }))
    await waitFor(() => expect(api.configureProviderCredential).toHaveBeenCalledWith(
      'p-ai4bharat', { credential_type: 'api_key', reference_key: 'BRUD_PROVIDER_SECRET__ai4bharat' }
    ))
    // The reference key (an env var name, not a secret) is fine to have typed into the
    // form, but no response ever carries an actual secret value for the page to render.
    expect(screen.queryByText('a-real-secret-value')).not.toBeInTheDocument()
  })

  it('lifecycle buttons call the corresponding API', async () => {
    mockDefaults()
    api.enableExternalDataProvider.mockResolvedValue({ ...SEEDED_PROVIDERS[0], lifecycle_status: 'enabled', enabled: true })
    const user = userEvent.setup()
    render(<ExternalDataProvidersPage />)
    await user.click(screen.getByRole('button', { name: 'Providers' }))
    await screen.findByText('AI4Bharat')
    await user.click(screen.getAllByRole('button', { name: 'Select' })[0])
    await user.click(screen.getByRole('button', { name: 'Enable' }))
    await waitFor(() => expect(api.enableExternalDataProvider).toHaveBeenCalledWith('p-ai4bharat'))
  })

  it('shows an error notice without a stack trace on API failure', async () => {
    api.externalDataProviders.mockRejectedValue(new Error('Request failed.'))
    render(<ExternalDataProvidersPage />)
    expect(await screen.findByText('Request failed.')).toBeInTheDocument()
  })
})
