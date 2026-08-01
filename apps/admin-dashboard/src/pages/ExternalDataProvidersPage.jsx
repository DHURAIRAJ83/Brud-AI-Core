import { useEffect, useState } from 'react'
import {
  addProviderDomain, archiveExternalDataProvider, blockExternalDataProvider,
  configureProviderCredential, disableExternalDataProvider, enableExternalDataProvider,
  externalDataProvider, externalDataProviders, providerCapabilities, providerConnectionTests,
  providerCredentialStatus, providerDomains, providerHistory, registerExternalDataProvider,
  restrictExternalDataProvider, revokeProviderCredential, setProviderCapabilities,
  testProviderConnection, verifyExternalDataProvider, verifyProviderDomain,
} from '../services/api.js'

const TABS = [
  'Overview', 'Providers', 'Add Provider', 'Domains', 'Capabilities', 'Credentials',
  'Connection Tests', 'History',
]

const PROVIDER_TYPES = [
  'dataset_catalogue', 'repository_host', 'government_portal', 'research_institution',
  'university_library', 'public_api', 'file_repository', 'custom_api', 'manual_source',
]
const ACCESS_MODES = ['public', 'gated', 'private', 'mixed', 'manual']
const AUTHENTICATION_TYPES = [
  'none', 'api_key', 'bearer_token', 'oauth', 'username_password', 'custom_header', 'manual_login',
]
const DOMAIN_TYPES = ['official', 'api', 'download', 'documentation', 'authentication', 'mirror']
const CAPABILITY_TYPES = [
  'search_datasets', 'read_metadata', 'read_dataset_card', 'read_licence', 'list_files',
  'download_sample', 'download_full', 'upload', 'write_metadata',
]
const DOWNLOAD_OR_WRITE_CAPABILITIES = new Set([
  'download_sample', 'download_full', 'upload', 'write_metadata',
])
const CREDENTIAL_TYPES = AUTHENTICATION_TYPES.filter((t) => t !== 'none')

const SAFETY_NOTICE = 'Registering, verifying, or enabling a provider never grants a dataset licence, RAG use, training use, or commercial use -- that remains a separate Source & Rights Registry decision for each piece of content later discovered. No dataset search, comparison, or download happens in this phase.'

const emptyProviderForm = {
  provider_code: '', name: '', provider_type: 'custom_api', description: '',
  official_website: '', catalogue_url: '', access_mode: 'manual', authentication_type: 'none',
  terms_url: '', support_url: '',
}

export default function ExternalDataProvidersPage() {
  const [tab, setTab] = useState('Overview')
  const [providersList, setProvidersList] = useState([])
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState('')

  const [selectedId, setSelectedId] = useState('')
  const [selected, setSelected] = useState(null)
  const [domains, setDomains] = useState([])
  const [capabilities, setCapabilities] = useState([])
  const [credentials, setCredentials] = useState([])
  const [connectionTests, setConnectionTests] = useState([])
  const [history, setHistory] = useState([])

  const [providerForm, setProviderForm] = useState(emptyProviderForm)
  const [domainForm, setDomainForm] = useState({ domain: '', domain_type: 'official' })
  const [domainEvidence, setDomainEvidence] = useState({})
  const [credentialForm, setCredentialForm] = useState({ credential_type: 'api_key', reference_key: '' })

  function loadProviders() {
    externalDataProviders('?page_size=100').then((data) => setProvidersList(data.items)).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadProviders() }, [])

  function selectProvider(publicId) {
    setSelectedId(publicId)
    // Clear the previous provider's detail immediately -- otherwise the
    // panel would keep showing the *previous* selection's name/status
    // (with its now-mismatched action buttons still clickable) until the
    // new fetch resolves, which could mislead an admin about which
    // provider a button click is about to act on.
    setSelected(null)
    setError(''); setNotice('')
    refreshSelected(publicId)
  }

  function refreshSelected(publicId = selectedId) {
    if (!publicId) return
    externalDataProvider(publicId).then(setSelected).catch((reason) => setError(reason.message))
    providerDomains(publicId).then((data) => setDomains(data.items)).catch(() => {})
    providerCapabilities(publicId).then((data) => setCapabilities(data.items)).catch(() => {})
    providerCredentialStatus(publicId).then((data) => setCredentials(data.items)).catch(() => {})
    providerConnectionTests(publicId).then((data) => setConnectionTests(data.items)).catch(() => {})
    providerHistory(publicId).then((data) => setHistory(data.items)).catch(() => {})
  }

  async function action(label, fn) {
    setBusy(label); setError(''); setNotice('')
    try {
      await fn()
      loadProviders()
      refreshSelected()
      setNotice(`${label}: done.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitProviderForm(event) {
    event.preventDefault()
    setBusy('Register provider'); setError('')
    try {
      const payload = { ...providerForm }
      for (const key of ['official_website', 'catalogue_url', 'terms_url', 'support_url']) {
        if (!payload[key]) delete payload[key]
      }
      const created = await registerExternalDataProvider(payload)
      setProviderForm(emptyProviderForm)
      loadProviders()
      setNotice(`Registered ${created.name} as ${created.lifecycle_status}/${created.trust_status}/disabled -- review and enable explicitly.`)
      setTab('Providers')
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitDomain(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Add domain', async () => {
      await addProviderDomain(selectedId, domainForm)
      setDomainForm({ domain: '', domain_type: 'official' })
    })
  }

  async function submitDomainVerification(domainId, verified) {
    const evidence = domainEvidence[domainId] || ''
    action(verified ? 'Verify domain' : 'Mark domain failed', () =>
      verifyProviderDomain(selectedId, domainId, { verified, evidence }))
  }

  function toggleCapability(capabilityType, enabled) {
    if (!selectedId) return
    const next = CAPABILITY_TYPES.filter((t) => !DOWNLOAD_OR_WRITE_CAPABILITIES.has(t)).map((t) => ({
      capability_type: t,
      enabled: t === capabilityType ? enabled : capabilities.find((c) => c.capability_type === t)?.enabled || false,
    }))
    action('Update capabilities', () => setProviderCapabilities(selectedId, { capabilities: next }))
  }

  async function submitCredential(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Configure credential reference', async () => {
      await configureProviderCredential(selectedId, credentialForm)
      setCredentialForm({ credential_type: 'api_key', reference_key: '' })
    })
  }

  const currentPage = <>
    <section className="intro">
      <div><span>Data provider registry</span><h2>External Data Providers</h2></div>
      <div className="phase-number">P9</div>
    </section>
    <div className="notice">{SAFETY_NOTICE}</div>
    {error && <div className="notice error-notice">{error}</div>}
    {notice && <div className="success-note">{notice}</div>}
    <nav aria-label="External Data Providers sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Overview' && <>
      <h3>Registered providers</h3>
      <section className="card-grid">
        <div className="status-card"><span>Total</span><strong>{providersList.length}</strong></div>
        <div className="status-card"><span>Enabled</span><strong>{providersList.filter((p) => p.enabled).length}</strong></div>
        <div className="status-card"><span>Verified (any tier)</span><strong>{providersList.filter((p) => p.trust_status !== 'unverified').length}</strong></div>
        <div className="status-card"><span>Blocked</span><strong>{providersList.filter((p) => p.lifecycle_status === 'blocked').length}</strong></div>
      </section>
      <p>Built-in templates (AI4Bharat, Hugging Face, GitHub, Wikimedia, Bhashini, and three generic templates) are seeded automatically, always starting draft/unverified/disabled. Nothing here is trusted or usable for discovery until an admin explicitly verifies and enables it.</p>
    </>}

    {tab === 'Providers' && <>
      <h3>Providers</h3>
      <table>
        <thead><tr>
          <th>Provider</th><th>Type</th><th>Access mode</th><th>Authentication</th><th>Trust</th>
          <th>Lifecycle</th><th>Anonymous read</th><th>Enabled</th><th></th>
        </tr></thead>
        <tbody>
          {providersList.map((item) => (
            <tr key={item.public_id}>
              <td>{item.name}<br /><small>{item.provider_code}</small></td>
              <td>{item.provider_type}</td>
              <td>{item.access_mode}</td>
              <td>{item.authentication_type}</td>
              <td>{item.trust_status}</td>
              <td>{item.lifecycle_status}</td>
              <td>{item.supports_anonymous_read ? 'yes' : 'no'}</td>
              <td>{item.enabled ? 'yes' : 'no'}</td>
              <td><button onClick={() => selectProvider(item.public_id)}>Select</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <div className="notice" style={{ marginTop: '1rem' }}>
        <h4>{selected.name} ({selected.provider_code})</h4>
        <p>{selected.description || 'No description recorded.'}</p>
        <p>trust_status: <strong>{selected.trust_status}</strong> · lifecycle_status: <strong>{selected.lifecycle_status}</strong> · enabled: <strong>{selected.enabled ? 'yes' : 'no'}</strong></p>
        <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
          <button disabled={!!busy} onClick={() => action('Verify', () => verifyExternalDataProvider(selectedId))}>Evaluate verification</button>
          <button disabled={!!busy} onClick={() => action('Enable', () => enableExternalDataProvider(selectedId))}>Enable</button>
          <button disabled={!!busy} onClick={() => action('Disable', () => disableExternalDataProvider(selectedId))}>Disable</button>
          <button disabled={!!busy} onClick={() => action('Restrict', () => restrictExternalDataProvider(selectedId))}>Restrict</button>
          <button disabled={!!busy} onClick={() => action('Block', () => blockExternalDataProvider(selectedId))}>Block</button>
          <button disabled={!!busy} onClick={() => action('Archive', () => archiveExternalDataProvider(selectedId))}>Archive</button>
        </div>
      </div>}
    </>}

    {tab === 'Add Provider' && <>
      <h3>Register a custom provider</h3>
      <p>New custom providers always start <strong>draft / unverified / disabled</strong> -- nothing here is trusted by registration alone.</p>
      <form onSubmit={submitProviderForm} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
        <label>Provider name<input required value={providerForm.name} onChange={(e) => setProviderForm({ ...providerForm, name: e.target.value })} /></label>
        <label>Provider code (stable, unique)<input required value={providerForm.provider_code} onChange={(e) => setProviderForm({ ...providerForm, provider_code: e.target.value })} /></label>
        <label>Provider type
          <select value={providerForm.provider_type} onChange={(e) => setProviderForm({ ...providerForm, provider_type: e.target.value })}>
            {PROVIDER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Access mode
          <select value={providerForm.access_mode} onChange={(e) => setProviderForm({ ...providerForm, access_mode: e.target.value })}>
            {ACCESS_MODES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Authentication type
          <select value={providerForm.authentication_type} onChange={(e) => setProviderForm({ ...providerForm, authentication_type: e.target.value })}>
            {AUTHENTICATION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Official website<input value={providerForm.official_website} onChange={(e) => setProviderForm({ ...providerForm, official_website: e.target.value })} placeholder="https://…" /></label>
        <label>Catalogue/API URL<input value={providerForm.catalogue_url} onChange={(e) => setProviderForm({ ...providerForm, catalogue_url: e.target.value })} /></label>
        <label>Terms URL<input value={providerForm.terms_url} onChange={(e) => setProviderForm({ ...providerForm, terms_url: e.target.value })} /></label>
        <label>Support URL<input value={providerForm.support_url} onChange={(e) => setProviderForm({ ...providerForm, support_url: e.target.value })} /></label>
        <label>Description<textarea rows={3} value={providerForm.description} onChange={(e) => setProviderForm({ ...providerForm, description: e.target.value })} /></label>
        <button type="submit" disabled={!!busy}>Register provider</button>
      </form>
    </>}

    {tab === 'Domains' && <>
      <h3>Domains{selected ? ` — ${selected.name}` : ''}</h3>
      {!selected && <p>Select a provider in the Providers tab first.</p>}
      {selected && <>
        <form onSubmit={submitDomain} style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', alignItems: 'flex-end', margin: '1rem 0' }}>
          <label>Domain<input required value={domainForm.domain} onChange={(e) => setDomainForm({ ...domainForm, domain: e.target.value })} placeholder="example.org" /></label>
          <label>Type
            <select value={domainForm.domain_type} onChange={(e) => setDomainForm({ ...domainForm, domain_type: e.target.value })}>
              {DOMAIN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <button type="submit" disabled={!!busy}>Add domain</button>
        </form>
        <table>
          <thead><tr><th>Domain</th><th>Type</th><th>Verification</th><th>Evidence</th><th></th></tr></thead>
          <tbody>
            {domains.map((d) => (
              <tr key={d.public_id}>
                <td>{d.domain}</td>
                <td>{d.domain_type}</td>
                <td>{d.verification_status}</td>
                <td>
                  <input placeholder="Verification evidence" value={domainEvidence[d.public_id] || ''} onChange={(e) => setDomainEvidence({ ...domainEvidence, [d.public_id]: e.target.value })} />
                </td>
                <td>
                  <button disabled={!!busy} onClick={() => submitDomainVerification(d.public_id, true)}>Mark verified</button>
                  <button disabled={!!busy} onClick={() => submitDomainVerification(d.public_id, false)}>Mark failed</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Capabilities' && <>
      <h3>Capabilities{selected ? ` — ${selected.name}` : ''}</h3>
      {!selected && <p>Select a provider in the Providers tab first.</p>}
      {selected && <>
        <p>Download, upload, and write-metadata capabilities can never be enabled in this phase -- shown for visibility only.</p>
        <table>
          <thead><tr><th>Capability</th><th>Enabled</th><th></th></tr></thead>
          <tbody>
            {CAPABILITY_TYPES.map((type) => {
              const existing = capabilities.find((c) => c.capability_type === type)
              const blocked = DOWNLOAD_OR_WRITE_CAPABILITIES.has(type)
              return (
                <tr key={type}>
                  <td>{type}</td>
                  <td>{existing?.enabled ? 'yes' : 'no'}</td>
                  <td>
                    {blocked
                      ? <em>never enabled in this phase</em>
                      : <button disabled={!!busy} onClick={() => toggleCapability(type, !existing?.enabled)}>{existing?.enabled ? 'Disable' : 'Enable'}</button>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Credentials' && <>
      <h3>Credentials{selected ? ` — ${selected.name}` : ''}</h3>
      {!selected && <p>Select a provider in the Providers tab first.</p>}
      {selected && <>
        <p>Only a credential <em>reference</em> (an environment variable name) is stored -- the actual secret value is never stored, logged, or returned by any API.</p>
        <form onSubmit={submitCredential} style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', alignItems: 'flex-end', margin: '1rem 0' }}>
          <label>Credential type
            <select value={credentialForm.credential_type} onChange={(e) => setCredentialForm({ ...credentialForm, credential_type: e.target.value })}>
              {CREDENTIAL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Environment variable name<input required value={credentialForm.reference_key} onChange={(e) => setCredentialForm({ ...credentialForm, reference_key: e.target.value })} placeholder="BRUD_PROVIDER_SECRET__…" /></label>
          <button type="submit" disabled={!!busy}>Configure reference</button>
        </form>
        <table>
          <thead><tr><th>Type</th><th>Configured</th><th>Status</th><th>Last tested</th></tr></thead>
          <tbody>
            {credentials.map((c) => (
              <tr key={c.credential_type}>
                <td>{c.credential_type}</td>
                <td>{c.configured ? 'yes' : 'no'}</td>
                <td>{c.status}</td>
                <td>{c.last_tested_at || 'never'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Connection Tests' && <>
      <h3>Connection Tests{selected ? ` — ${selected.name}` : ''}</h3>
      {!selected && <p>Select a provider in the Providers tab first.</p>}
      {selected && <>
        <div style={{ display: 'flex', gap: '.5rem', margin: '1rem 0' }}>
          <button disabled={!!busy} onClick={() => action('Test connection', () => testProviderConnection(selectedId, { use_credential: false }))}>Test connection (anonymous)</button>
          <button disabled={!!busy} onClick={() => action('Test connection with credential', () => testProviderConnection(selectedId, { use_credential: true }))}>Test connection (with credential)</button>
        </div>
        <table>
          <thead><tr><th>Result</th><th>Latency (ms)</th><th>Error</th><th>Tested at</th></tr></thead>
          <tbody>
            {connectionTests.map((t) => (
              <tr key={t.public_id}>
                <td>{t.result}</td>
                <td>{t.latency_ms ?? '—'}</td>
                <td>{t.error_code || '—'}</td>
                <td>{t.tested_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'History' && <>
      <h3>History{selected ? ` — ${selected.name}` : ''}</h3>
      {!selected && <p>Select a provider in the Providers tab first.</p>}
      {selected && <div className="audit-list">
        {history.map((event) => (
          <article key={event.public_id}>
            <div><strong>{event.event_type.replaceAll('_', ' ')}</strong><span>{event.performed_by_admin_public_id}</span></div>
            <small>{event.summary} — {event.created_at}</small>
          </article>
        ))}
      </div>}
    </>}
  </>

  return currentPage
}
