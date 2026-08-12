import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const pgSubTabs = [
  'Overview', 'Plugin Registry', 'Validation', 'Capabilities', 'Risk Analysis', 'Sandbox',
  'Filesystem', 'Network', 'Permissions', 'Consents', 'Runtime Events', 'Reports', 'Diagnostics',
]

export default function PluginGovernanceTab({
  pgSubTab, setPgSubTab,
  pgDiag, pgPluginsList, pgMemoryList, pgPluginData, pgBusy,
  runPgValidate, runPgClassify, runPgRiskScore, runPgSandbox, runPgFilesystemPolicy, runPgNetworkPolicy, runPgEnable,
  submitPgRegister, pgForm, setPgForm,
  pgSelectedPluginId, selectPgPlugin,
  submitPgEvaluate, pgEvalScopeKey, setPgEvalScopeKey, pgEvalIsPublicChat, setPgEvalIsPublicChat, pgEvalUserIdHash, setPgEvalUserIdHash,
  runPgPolicyCheck, pgEvalResult, pgPolicyCheckResult, pgPermissionsList, runPgGrant, runPgRevoke,
  submitPgConsent, pgConsentScopeKey, setPgConsentScopeKey, pgConsentUserIdentity, setPgConsentUserIdentity,
  pgConsentGiven, setPgConsentGiven, pgConsentTtl, setPgConsentTtl, pgConsentsList,
  submitPgIssueToken, pgTokenScopeKeys, setPgTokenScopeKeys, pgTokenUserIdentity, setPgTokenUserIdentity,
  pgTokenSessionIdentity, setPgTokenSessionIdentity, pgTokenTtl, setPgTokenTtl, pgTokenResult,
  runPgReportExecution, runPgGenerateReport, runPgDisable, runPgArchive, pgEventsList,
}) {
  return (
    <>
      <p className="notice">
        MB-24 -- Plugin &amp; Tool Runtime Governance Center. This is the policy, permission,
        consent, sandbox, audit, and execution-governance layer -- not a marketplace, not a
        deployment engine, not a real sandbox. No plugin binary is ever executed. Every plugin is
        born disabled and every permission is born ungranted; only an explicit admin action here
        can change either.
      </p>

      <div className="dataset-tabs">
        {pgSubTabs.map((t) => (
          <Button key={t} className={pgSubTab === t ? 'active' : ''} onClick={() => setPgSubTab(t)}>{t}</Button>
        ))}
      </div>

      {pgSubTab === 'Overview' && (
        <>
          {pgDiag && (
            <div className="notice">
              <p><strong>Plugins start disabled:</strong> {String(pgDiag.plugins_start_disabled)} -- <strong>Auto-enable performed:</strong> {String(pgDiag.auto_enable_after_upload_performed)} -- <strong>Auto permission grant performed:</strong> {String(pgDiag.auto_permission_grant_performed)}</p>
              <p><strong>Plugin binaries ever executed:</strong> {String(pgDiag.plugin_binaries_ever_executed)} -- <strong>Real sandbox/OS isolation exists:</strong> {String(pgDiag.real_sandbox_or_os_isolation_exists)}</p>
            </div>
          )}
          <section className="metric-grid">
            <StatusCard label="Registered plugins" value={pgPluginsList.length} tone="neutral" />
            <StatusCard label="Archived (permanent record)" value={pgMemoryList.length} tone="neutral" />
          </section>
          {!pgPluginData && <div className="notice">Select or register a plugin in the Plugin Registry sub-tab first.</div>}
          {pgPluginData && (
            <div className="notice">
              <section className="metric-grid">
                <StatusCard label="Name" value={pgPluginData.name.slice(0, 24)} tone="neutral" />
                <StatusCard label="Stage" value={pgPluginData.stage} tone="neutral" />
                <StatusCard label="Status" value={pgPluginData.status} tone="neutral" />
                <StatusCard label="Risk level" value={pgPluginData.risk_level || 'n/a'} tone="neutral" />
              </section>
              <h4>Advance workflow</h4>
              {pgPluginData.stage === 'register' && <Button onClick={runPgValidate} disabled={pgBusy}>Validate manifest</Button>}
              {pgPluginData.stage === 'validate_manifest' && <Button onClick={runPgClassify} disabled={pgBusy}>Classify capabilities</Button>}
              {pgPluginData.stage === 'classify_capabilities' && <Button onClick={runPgRiskScore} disabled={pgBusy}>Compute risk score</Button>}
              {pgPluginData.stage === 'compute_risk' && <Button onClick={runPgSandbox} disabled={pgBusy}>Build sandbox profile</Button>}
              {pgPluginData.stage === 'build_sandbox' && <Button onClick={runPgFilesystemPolicy} disabled={pgBusy}>Build filesystem policy</Button>}
              {pgPluginData.stage === 'build_filesystem_policy' && <Button onClick={runPgNetworkPolicy} disabled={pgBusy}>Build network policy</Button>}
              {pgPluginData.stage === 'build_network_policy' && pgPluginData.status === 'disabled' && (
                <Button onClick={runPgEnable} disabled={pgBusy}>Enable plugin (admin review)</Button>
              )}
              {pgPluginData.stage === 'evaluate_permission' && <p>Evaluate and grant permissions in the Permissions sub-tab.</p>}
              {pgPluginData.stage === 'grant_permission' && <p>Issue an execution token in the Runtime Events sub-tab.</p>}
              {pgPluginData.stage === 'issue_token' && <p>Generate the governance report in the Reports sub-tab.</p>}
              {pgPluginData.stage === 'governance_report' && <p>Disable and archive in the Runtime Events sub-tab.</p>}
              {pgPluginData.stage === 'archived' && <p>This plugin is archived. See Reports for its permanent record.</p>}
            </div>
          )}
        </>
      )}

      {pgSubTab === 'Plugin Registry' && (
        <>
          <form className="inline-form training-form" onSubmit={submitPgRegister}>
            <label>Plugin ID<input value={pgForm.plugin_id} onChange={(e) => setPgForm({ ...pgForm, plugin_id: e.target.value })} required /></label>
            <label>Name<input value={pgForm.name} onChange={(e) => setPgForm({ ...pgForm, name: e.target.value })} required /></label>
            <label>Version<input value={pgForm.version} onChange={(e) => setPgForm({ ...pgForm, version: e.target.value })} required /></label>
            <label>Author<input value={pgForm.author} onChange={(e) => setPgForm({ ...pgForm, author: e.target.value })} /></label>
            <label>Description<input value={pgForm.description} onChange={(e) => setPgForm({ ...pgForm, description: e.target.value })} /></label>
            <label>Entrypoint<input value={pgForm.entrypoint} onChange={(e) => setPgForm({ ...pgForm, entrypoint: e.target.value })} required /></label>
            <label>Requested scopes (comma-separated)<input value={pgForm.requested_scopes} onChange={(e) => setPgForm({ ...pgForm, requested_scopes: e.target.value })} placeholder="filesystem.read.user_selected, network.http.allowed_domains" /></label>
            <label>Allowed domains (comma-separated)<input value={pgForm.allowed_domains} onChange={(e) => setPgForm({ ...pgForm, allowed_domains: e.target.value })} /></label>
            <label>Filesystem roots (comma-separated)<input value={pgForm.filesystem_roots} onChange={(e) => setPgForm({ ...pgForm, filesystem_roots: e.target.value })} /></label>
            <label>UI components (comma-separated)<input value={pgForm.ui_components} onChange={(e) => setPgForm({ ...pgForm, ui_components: e.target.value })} /></label>
            <label><input type="checkbox" checked={pgForm.local_storage_usage} onChange={(e) => setPgForm({ ...pgForm, local_storage_usage: e.target.checked })} /> Local storage usage</label>
            <label><input type="checkbox" checked={pgForm.cloud_storage_usage} onChange={(e) => setPgForm({ ...pgForm, cloud_storage_usage: e.target.checked })} /> Cloud storage usage</label>
            <label>Minimum Brud version<input value={pgForm.minimum_brud_version} onChange={(e) => setPgForm({ ...pgForm, minimum_brud_version: e.target.value })} /></label>
            <label>Signature placeholder<input value={pgForm.signature_placeholder} onChange={(e) => setPgForm({ ...pgForm, signature_placeholder: e.target.value })} /></label>
            <label>Homepage<input value={pgForm.homepage} onChange={(e) => setPgForm({ ...pgForm, homepage: e.target.value })} /></label>
            <label>Support URL<input value={pgForm.support_url} onChange={(e) => setPgForm({ ...pgForm, support_url: e.target.value })} /></label>
            <label>Source
              <select value={pgForm.source} onChange={(e) => setPgForm({ ...pgForm, source: e.target.value })}>
                <option value="manual_upload">manual_upload</option>
                <option value="local_development">local_development</option>
                <option value="marketplace_reference">marketplace_reference</option>
              </select>
            </label>
            <Button type="submit" disabled={pgBusy}>{pgBusy ? 'Working…' : 'Register plugin'}</Button>
          </form>
          <ul className="notice">
            {pgPluginsList.map((p) => (
              <li key={p.public_id}>
                <Button className={pgSelectedPluginId === p.public_id ? 'active' : ''} onClick={() => selectPgPlugin(p.public_id)}>
                  {p.name} v{p.version} -- {p.stage} -- {p.status} -- risk: {p.risk_level || 'n/a'}
                </Button>
              </li>
            ))}
            {!pgPluginsList.length && <li>No plugins registered yet.</li>}
          </ul>
        </>
      )}

      {pgSubTab === 'Validation' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.validation_report, null, 2)}</pre>}
        </>
      )}

      {pgSubTab === 'Capabilities' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.capability_classification, null, 2)}</pre>}
        </>
      )}

      {pgSubTab === 'Risk Analysis' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && (
            <section className="metric-grid">
              <StatusCard label="Risk score" value={pgPluginData.risk_score ?? 'n/a'} tone="neutral" />
              <StatusCard label="Risk level" value={pgPluginData.risk_level || 'n/a'} tone="neutral" />
            </section>
          )}
        </>
      )}

      {pgSubTab === 'Sandbox' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.sandbox_profile, null, 2)}</pre>}
        </>
      )}

      {pgSubTab === 'Filesystem' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.filesystem_policy, null, 2)}</pre>}
        </>
      )}

      {pgSubTab === 'Network' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.network_policy, null, 2)}</pre>}
        </>
      )}

      {pgSubTab === 'Permissions' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && (
            <>
              <form className="inline-form training-form" onSubmit={submitPgEvaluate}>
                <label>Scope key<input value={pgEvalScopeKey} onChange={(e) => setPgEvalScopeKey(e.target.value)} placeholder="filesystem.read.user_selected" required /></label>
                <label><input type="checkbox" checked={pgEvalIsPublicChat} onChange={(e) => setPgEvalIsPublicChat(e.target.checked)} /> Is public chat</label>
                <label>User ID hash (optional)<input value={pgEvalUserIdHash} onChange={(e) => setPgEvalUserIdHash(e.target.value)} /></label>
                <Button type="submit" disabled={pgBusy}>Evaluate permission</Button>
                <Button type="button" onClick={runPgPolicyCheck} disabled={pgBusy || !pgEvalScopeKey}>Preview public policy check</Button>
              </form>
              {pgEvalResult && <pre className="notice">{JSON.stringify(pgEvalResult, null, 2)}</pre>}
              {pgPolicyCheckResult && <pre className="notice">{JSON.stringify(pgPolicyCheckResult, null, 2)}</pre>}
              <ul className="notice">
                {pgPermissionsList.map((p) => (
                  <li key={p.public_id}>
                    {p.scope_key} -- decision: {p.decision} -- status: {p.status}
                    {p.status !== 'granted' && (
                      <Button onClick={() => runPgGrant(p.scope_key, pgEvalUserIdHash)} disabled={pgBusy}>Grant</Button>
                    )}
                    {p.status === 'granted' && (
                      <Button onClick={() => runPgRevoke(p.scope_key)} disabled={pgBusy}>Revoke</Button>
                    )}
                  </li>
                ))}
                {!pgPermissionsList.length && <li>No permission evaluations recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {pgSubTab === 'Consents' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && (
            <>
              <form className="inline-form training-form" onSubmit={submitPgConsent}>
                <label>Scope key<input value={pgConsentScopeKey} onChange={(e) => setPgConsentScopeKey(e.target.value)} required /></label>
                <label>Raw user identity<input value={pgConsentUserIdentity} onChange={(e) => setPgConsentUserIdentity(e.target.value)} placeholder="never stored raw -- hashed immediately" required /></label>
                <label><input type="checkbox" checked={pgConsentGiven} onChange={(e) => setPgConsentGiven(e.target.checked)} /> Consent given</label>
                <label>TTL seconds (optional)<input value={pgConsentTtl} onChange={(e) => setPgConsentTtl(e.target.value)} /></label>
                <Button type="submit" disabled={pgBusy}>Record consent</Button>
              </form>
              <ul className="notice">
                {pgConsentsList.map((c) => (
                  <li key={c.public_id}>{c.scope_key} -- given: {String(c.consent_given)} -- user {c.user_id_hash.slice(0, 12)}… -- expires: {c.expires_at || 'never'}</li>
                ))}
                {!pgConsentsList.length && <li>No consent records yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {pgSubTab === 'Runtime Events' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && (
            <>
              <form className="inline-form training-form" onSubmit={submitPgIssueToken}>
                <label>Scope keys (comma-separated, must already be granted)<input value={pgTokenScopeKeys} onChange={(e) => setPgTokenScopeKeys(e.target.value)} required /></label>
                <label>Raw user identity<input value={pgTokenUserIdentity} onChange={(e) => setPgTokenUserIdentity(e.target.value)} required /></label>
                <label>Raw session identity<input value={pgTokenSessionIdentity} onChange={(e) => setPgTokenSessionIdentity(e.target.value)} required /></label>
                <label>TTL seconds<input value={pgTokenTtl} onChange={(e) => setPgTokenTtl(e.target.value)} /></label>
                <Button type="submit" disabled={pgBusy}>Issue execution token</Button>
              </form>
              {pgTokenResult && (
                <div className="notice">
                  <p>Only the token hash is ever persisted -- shown once, here, and never stored raw.</p>
                  <pre>{JSON.stringify(pgTokenResult, null, 2)}</pre>
                </div>
              )}
              <div className="notice">
                <Button onClick={runPgReportExecution} disabled={pgBusy}>Record an external execution report</Button>
                <Button onClick={runPgGenerateReport} disabled={pgBusy}>Generate governance report</Button>
                {pgPluginData.status === 'enabled' && <Button onClick={runPgDisable} disabled={pgBusy}>Disable plugin</Button>}
                {(pgPluginData.status === 'disabled' || pgPluginData.status === 'enabled') && (
                  <Button onClick={runPgArchive} disabled={pgBusy}>Archive plugin</Button>
                )}
              </div>
              <h4>Event log</h4>
              <ul className="notice">
                {pgEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.stage || 'n/a'} -- {e.message}</li>)}
                {!pgEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {pgSubTab === 'Reports' && (
        <>
          {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
          {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.governance_report, null, 2)}</pre>}
          <h4>Permanent archive record</h4>
          <ul className="notice">
            {pgMemoryList.map((m) => (
              <li key={m.public_id}>{m.created_at} -- final_status: {m.final_status} -- granted: {m.total_permissions_granted} -- consents: {m.total_consents_recorded} -- events: {m.total_runtime_events} -- risk: {m.risk_level || 'n/a'}</li>
            ))}
            {!pgMemoryList.length && <li>No archived plugins yet.</li>}
          </ul>
        </>
      )}

      {pgSubTab === 'Diagnostics' && (
        <>
          {pgDiag && <pre className="notice">{JSON.stringify(pgDiag, null, 2)}</pre>}
          {!pgDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
