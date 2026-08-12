import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PluginGovernanceTab from './PluginGovernanceTab.jsx'

function baseProps(overrides = {}) {
  return {
    pgSubTab: 'Overview',
    setPgSubTab: vi.fn(),
    pgDiag: null,
    pgPluginsList: [],
    pgMemoryList: [],
    pgPluginData: null,
    pgBusy: false,
    runPgValidate: vi.fn(),
    runPgClassify: vi.fn(),
    runPgRiskScore: vi.fn(),
    runPgSandbox: vi.fn(),
    runPgFilesystemPolicy: vi.fn(),
    runPgNetworkPolicy: vi.fn(),
    runPgEnable: vi.fn(),
    submitPgRegister: vi.fn((event) => event?.preventDefault?.()),
    pgForm: {
      plugin_id: '', name: '', version: '', author: '', description: '', entrypoint: '',
      requested_scopes: '', allowed_domains: '', filesystem_roots: '', ui_components: '',
      local_storage_usage: false, cloud_storage_usage: false, minimum_brud_version: '',
      signature_placeholder: '', homepage: '', support_url: '', source: 'manual_upload',
    },
    setPgForm: vi.fn(),
    pgSelectedPluginId: '',
    selectPgPlugin: vi.fn(),
    submitPgEvaluate: vi.fn((event) => event?.preventDefault?.()),
    pgEvalScopeKey: '',
    setPgEvalScopeKey: vi.fn(),
    pgEvalIsPublicChat: false,
    setPgEvalIsPublicChat: vi.fn(),
    pgEvalUserIdHash: '',
    setPgEvalUserIdHash: vi.fn(),
    runPgPolicyCheck: vi.fn(),
    pgEvalResult: null,
    pgPolicyCheckResult: null,
    pgPermissionsList: [],
    runPgGrant: vi.fn(),
    runPgRevoke: vi.fn(),
    submitPgConsent: vi.fn((event) => event?.preventDefault?.()),
    pgConsentScopeKey: '',
    setPgConsentScopeKey: vi.fn(),
    pgConsentUserIdentity: '',
    setPgConsentUserIdentity: vi.fn(),
    pgConsentGiven: false,
    setPgConsentGiven: vi.fn(),
    pgConsentTtl: '',
    setPgConsentTtl: vi.fn(),
    pgConsentsList: [],
    submitPgIssueToken: vi.fn((event) => event?.preventDefault?.()),
    pgTokenScopeKeys: '',
    setPgTokenScopeKeys: vi.fn(),
    pgTokenUserIdentity: '',
    setPgTokenUserIdentity: vi.fn(),
    pgTokenSessionIdentity: '',
    setPgTokenSessionIdentity: vi.fn(),
    pgTokenTtl: '',
    setPgTokenTtl: vi.fn(),
    pgTokenResult: null,
    runPgReportExecution: vi.fn(),
    runPgGenerateReport: vi.fn(),
    runPgDisable: vi.fn(),
    runPgArchive: vi.fn(),
    pgEventsList: [],
    ...overrides,
  }
}

describe('PluginGovernanceTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setPgSubTab = vi.fn()
    render(<PluginGovernanceTab {...baseProps({ setPgSubTab })} />)
    for (const label of ['Overview', 'Plugin Registry', 'Validation', 'Capabilities', 'Risk Analysis', 'Sandbox', 'Filesystem', 'Network', 'Permissions', 'Consents', 'Runtime Events', 'Reports', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Sandbox' }))
    expect(setPgSubTab).toHaveBeenCalledWith('Sandbox')
  })

  it('Plugin Registry: submits a real registration form', async () => {
    const user = userEvent.setup()
    const submitPgRegister = vi.fn((event) => event?.preventDefault?.())
    render(<PluginGovernanceTab {...baseProps({
      pgSubTab: 'Plugin Registry',
      pgForm: {
        plugin_id: 'plugin-1', name: 'My Plugin', version: '1.0.0', author: '', description: '', entrypoint: 'main.py',
        requested_scopes: '', allowed_domains: '', filesystem_roots: '', ui_components: '',
        local_storage_usage: false, cloud_storage_usage: false, minimum_brud_version: '',
        signature_placeholder: '', homepage: '', support_url: '', source: 'manual_upload',
      },
      submitPgRegister,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Register plugin' }))
    expect(submitPgRegister).toHaveBeenCalled()
  })

  it('Overview: real advance-workflow button calls the handler', async () => {
    const user = userEvent.setup()
    const runPgValidate = vi.fn()
    render(<PluginGovernanceTab {...baseProps({
      pgPluginData: { name: 'My Plugin', stage: 'register', status: 'disabled' },
      runPgValidate,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Validate manifest' }))
    expect(runPgValidate).toHaveBeenCalled()
  })

  it('Permissions: real grant button calls the handler with the right scope', async () => {
    const user = userEvent.setup()
    const runPgGrant = vi.fn()
    render(<PluginGovernanceTab {...baseProps({
      pgSubTab: 'Permissions',
      pgPluginData: { name: 'My Plugin', stage: 'evaluate_permission', status: 'disabled' },
      pgPermissionsList: [{ public_id: 'perm-1', scope_key: 'filesystem.read.user_selected', decision: 'allow', status: 'evaluated' }],
      runPgGrant,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Grant' }))
    expect(runPgGrant).toHaveBeenCalledWith('filesystem.read.user_selected', '')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<PluginGovernanceTab {...baseProps({ pgSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
