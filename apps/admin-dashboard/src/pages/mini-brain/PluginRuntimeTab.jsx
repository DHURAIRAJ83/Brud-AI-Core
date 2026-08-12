import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const prSubTabs = [
  'Overview', 'Execute', 'Active Executions', 'Results', 'Filesystem', 'Network', 'Permissions',
  'Consents', 'Public Chat', 'Admin Assistant', 'Audit', 'History', 'Diagnostics',
]

export default function PluginRuntimeTab({
  prSubTab, setPrSubTab,
  prDiag, prStats,
  submitPrExecute, prExecForm, setPrExecForm, prBusy, prExecResult,
  prExecutionsList, prSelectedExecutionId, selectPrExecution, runPrCancel,
  prExecutionData, prLogs, runPrGenerateReport, runPrArchive, prReportResult,
  submitPrPublicExecute, prPublicForm, setPrPublicForm, prPublicResult,
  runPrReportEvent,
  prMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-25 -- Secure Plugin Execution Runtime. The first phase that actually runs plugin
        code -- but only an admin-approved, on-disk file loaded via <code>importlib</code>
        (never <code>eval</code>/<code>exec</code>, never a shell, never code from a chat
        message), and only after MB-24's own permission and consent decisions are re-derived
        fresh, from MB-24's own database records, on every single execution. No container or
        process isolation exists in this phase -- guards are cooperative, not adversarially
        enforced.
      </p>

      <div className="dataset-tabs">
        {prSubTabs.map((t) => (
          <Button key={t} className={prSubTab === t ? 'active' : ''} onClick={() => setPrSubTab(t)}>{t}</Button>
        ))}
      </div>

      {prSubTab === 'Overview' && (
        <>
          {prDiag && (
            <div className="notice">
              <p><strong>Container isolation exists:</strong> {String(prDiag.container_isolation_exists)} -- <strong>Process isolation exists:</strong> {String(prDiag.process_isolation_exists)} -- <strong>Shell commands executed:</strong> {String(prDiag.shell_commands_executed)}</p>
              <p><strong>Consent bypassed:</strong> {String(prDiag.consent_bypassed)} -- <strong>Admin review bypassed:</strong> {String(prDiag.admin_review_bypassed)} -- <strong>Admin-only scopes reachable from public chat:</strong> {String(prDiag.admin_only_scopes_accessible_from_public_chat)}</p>
            </div>
          )}
          {prStats && (
            <section className="metric-grid">
              <StatusCard label="Total executions" value={prStats.total_executions} tone="neutral" />
              <StatusCard label="Completed" value={prStats.executions_by_status?.completed || 0} tone="good" />
              <StatusCard label="Denied" value={prStats.executions_by_status?.denied || 0} tone="warn" />
              <StatusCard label="Avg duration (ms)" value={prStats.average_duration_ms ? prStats.average_duration_ms.toFixed(2) : 'n/a'} tone="neutral" />
            </section>
          )}
        </>
      )}

      {prSubTab === 'Execute' && (
        <>
          <p className="notice">
            Requires a real execution token issued from the Plugin Governance tab's Runtime
            Events sub-tab (<code>pgIssueToken</code>). Paste the full returned token JSON
            below -- only its hash is ever persisted, never the raw token.
          </p>
          <form className="inline-form training-form" onSubmit={submitPrExecute}>
            <label>Plugin public ID<input value={prExecForm.plugin_public_id} onChange={(e) => setPrExecForm({ ...prExecForm, plugin_public_id: e.target.value })} required /></label>
            <label>Scope key<input value={prExecForm.scope_key} onChange={(e) => setPrExecForm({ ...prExecForm, scope_key: e.target.value })} placeholder="network.http.allowed_domains" required /></label>
            <label>Arguments (JSON)<textarea rows={3} value={prExecForm.arguments} onChange={(e) => setPrExecForm({ ...prExecForm, arguments: e.target.value })} /></label>
            <label>Execution token (JSON)<textarea rows={4} value={prExecForm.execution_token} onChange={(e) => setPrExecForm({ ...prExecForm, execution_token: e.target.value })} required /></label>
            <label>Timeout seconds<input value={prExecForm.timeout_seconds} onChange={(e) => setPrExecForm({ ...prExecForm, timeout_seconds: e.target.value })} /></label>
            <Button type="submit" disabled={prBusy}>{prBusy ? 'Executing…' : 'Execute'}</Button>
          </form>
          {prExecResult && <pre className="notice">{JSON.stringify(prExecResult, null, 2)}</pre>}
        </>
      )}

      {prSubTab === 'Active Executions' && (
        <>
          <ul className="notice">
            {prExecutionsList.map((e) => (
              <li key={e.public_id}>
                <Button className={prSelectedExecutionId === e.public_id ? 'active' : ''} onClick={() => selectPrExecution(e.public_id)}>
                  {e.plugin_public_id.slice(0, 8)}… -- {e.execution_mode} -- {e.status} -- {e.scope_key}
                </Button>
                {e.status === 'pending' && prSelectedExecutionId === e.public_id && (
                  <Button onClick={runPrCancel} disabled={prBusy}>Cancel</Button>
                )}
              </li>
            ))}
            {!prExecutionsList.length && <li>No executions recorded yet.</li>}
          </ul>
        </>
      )}

      {prSubTab === 'Results' && (
        <>
          {!prExecutionData && <div className="notice">Select an execution in Active Executions first.</div>}
          {prExecutionData && (
            <>
              <section className="metric-grid">
                <StatusCard label="Status" value={prExecutionData.status} tone="neutral" />
                <StatusCard label="Duration (ms)" value={prExecutionData.duration_ms ?? 'n/a'} tone="neutral" />
              </section>
              {prExecutionData.denial_reason && <div className="notice">Denial reason: {prExecutionData.denial_reason}</div>}
              <h4>Sanitized input/output</h4>
              <ul className="notice">
                {(prLogs?.io || []).map((io) => (
                  <li key={io.public_id}>{io.io_type} -- truncated: {String(io.truncated)} -- redactions: {(io.redaction_categories || []).join(', ') || 'none'}<pre>{io.sanitized_payload?.text}</pre></li>
                ))}
                {!(prLogs?.io || []).length && <li>No sanitized input/output recorded yet.</li>}
              </ul>
              <div className="notice">
                <Button onClick={runPrGenerateReport} disabled={prBusy}>Generate report</Button>
                {['completed', 'failed', 'timeout', 'denied', 'cancelled'].includes(prExecutionData.status) && (
                  <Button onClick={runPrArchive} disabled={prBusy}>Archive execution</Button>
                )}
              </div>
              {prReportResult && <pre className="notice">{JSON.stringify(prReportResult, null, 2)}</pre>}
            </>
          )}
        </>
      )}

      {prSubTab === 'Filesystem' && (
        <div className="notice">
          Filesystem access is governed entirely by MB-24's own <code>filesystem_policy</code>
          for the plugin being executed -- see the Plugin Governance tab's Filesystem sub-tab
          for the actual approved roots. Any path a plugin declares outside those roots is
          blocked before execution and shows up here as a <code>denied</code> execution whose
          <code>denial_reason</code> mentions &quot;outside every filesystem root&quot;.
        </div>
      )}

      {prSubTab === 'Network' && (
        <div className="notice">
          Network access is governed entirely by MB-24's own <code>network_policy</code>
          allowed-domains list for the plugin being executed -- see the Plugin Governance
          tab's Network sub-tab for the actual approved domains. Any domain a plugin declares
          outside that list is blocked before execution and shows up here as a
          <code>denied</code> execution whose <code>denial_reason</code> mentions &quot;not in
          the approved allowed_domains list&quot;.
        </div>
      )}

      {prSubTab === 'Permissions' && (
        <>
          <p className="notice">
            MB-25 never trusts a cached decision -- the scope's grant status is re-queried
            from MB-24's own permission records on every execution. A <code>denied</code>
            execution whose <code>denial_reason</code> mentions &quot;not currently
            granted&quot; means the permission gate failed.
          </p>
          {prExecutionData && (
            <div className="notice">Selected execution scope: <strong>{prExecutionData.scope_key}</strong> -- granted scopes at execution time: {(prExecutionData.granted_scopes || []).join(', ') || 'none'}</div>
          )}
        </>
      )}

      {prSubTab === 'Consents' && (
        <>
          <p className="notice">
            Consent validity (including expiry) is re-checked fresh from MB-24's own consent
            records on every execution. A <code>denied</code> execution whose
            <code>denial_reason</code> mentions &quot;requires valid&quot; means the consent
            gate failed.
          </p>
          {prExecutionData && (
            <div className="notice">Selected execution requester: {prExecutionData.requester_user_id_hash ? `${prExecutionData.requester_user_id_hash.slice(0, 12)}…` : 'n/a (admin-initiated)'}</div>
          )}
        </>
      )}

      {prSubTab === 'Public Chat' && (
        <>
          <p className="notice">
            Demonstrates the fully public <code>/api/public/plugin-runtime/execute</code>
            route (no admin auth, rate-limited) -- <code>execution_mode</code> is always
            forced to <code>public_chat</code> server-side.
          </p>
          <form className="inline-form training-form" onSubmit={submitPrPublicExecute}>
            <label>Plugin public ID<input value={prPublicForm.plugin_public_id} onChange={(e) => setPrPublicForm({ ...prPublicForm, plugin_public_id: e.target.value })} required /></label>
            <label>Scope key<input value={prPublicForm.scope_key} onChange={(e) => setPrPublicForm({ ...prPublicForm, scope_key: e.target.value })} required /></label>
            <label>Arguments (JSON)<textarea rows={3} value={prPublicForm.arguments} onChange={(e) => setPrPublicForm({ ...prPublicForm, arguments: e.target.value })} /></label>
            <label>Raw user identity<input value={prPublicForm.raw_user_identity} onChange={(e) => setPrPublicForm({ ...prPublicForm, raw_user_identity: e.target.value })} required /></label>
            <label>Execution token (JSON)<textarea rows={4} value={prPublicForm.execution_token} onChange={(e) => setPrPublicForm({ ...prPublicForm, execution_token: e.target.value })} required /></label>
            <Button type="submit" disabled={prBusy}>{prBusy ? 'Executing…' : 'Execute as public chat'}</Button>
          </form>
          {prPublicResult && <pre className="notice">{JSON.stringify(prPublicResult, null, 2)}</pre>}
        </>
      )}

      {prSubTab === 'Admin Assistant' && (
        <>
          <p className="notice">
            Admin Assistant executions pass through the exact same policy re-verification as
            any other caller -- Admin Assistant is not a bypass.
          </p>
          <ul className="notice">
            {prExecutionsList.filter((e) => e.execution_mode === 'admin_assistant').map((e) => (
              <li key={e.public_id}>{e.public_id.slice(0, 8)}… -- {e.status} -- {e.scope_key} -- {e.created_at}</li>
            ))}
            {!prExecutionsList.filter((e) => e.execution_mode === 'admin_assistant').length && <li>No Admin Assistant executions yet.</li>}
          </ul>
        </>
      )}

      {prSubTab === 'Audit' && (
        <>
          {!prExecutionData && <div className="notice">Select an execution in Active Executions first.</div>}
          {prExecutionData && (
            <>
              <Button onClick={runPrReportEvent} disabled={prBusy}>Record an admin note</Button>
              <ul className="notice">
                {(prLogs?.events || []).map((ev) => <li key={ev.public_id}>{ev.created_at} -- {ev.event_type} -- {ev.stage || 'n/a'} -- {ev.message}</li>)}
                {!(prLogs?.events || []).length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {prSubTab === 'History' && (
        <ul className="notice">
          {prMemoryList.map((m) => (
            <li key={m.public_id}>{m.created_at} -- plugin {m.plugin_public_id.slice(0, 8)}… -- final_status: {m.final_status} -- duration: {m.duration_ms ?? 'n/a'}ms -- guard violations: {m.guard_violation_count} -- recorded by: {m.recorded_by}</li>
          ))}
          {!prMemoryList.length && <li>No archived executions yet.</li>}
        </ul>
      )}

      {prSubTab === 'Diagnostics' && (
        <>
          {prDiag && <pre className="notice">{JSON.stringify(prDiag, null, 2)}</pre>}
          {!prDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
