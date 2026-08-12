import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'
import ChatPanel from '../../components/chat/ChatPanel.jsx'

const lrSubTabs = [
  'Chat', 'Explain Page', 'Summarize Report', 'Summarize Regression', 'Explain Error',
  'Next Actions', 'Local Model Config', 'Diagnostics',
]

export default function AssistantIntelligenceTab({
  admin, toast,
  lrDiag,
  lrSubTab, setLrSubTab,
  submitLrExplainPage, lrExplainPageForm, setLrExplainPageForm, lrBusy,
  submitLrSummarizeReport, lrReportForm, setLrReportForm,
  submitLrSummarizeRegression, lrRegressionForm, setLrRegressionForm,
  submitLrExplainError, lrErrorForm, setLrErrorForm,
  submitLrNextActions, lrStatusSnapshotForm, setLrStatusSnapshotForm, lrNextActionsResult,
  lrLocalModelConfig, setLrLocalModelConfig, saveLrLocalModelConfig,
}) {
  return (
    <>
      <p className="notice">
        MB-28 -- Real Mini Brain LLM Runtime &amp; Admin Assistant Intelligence Layer. Local-first,
        CPU-first reasoning for admins only -- prefers a local model, falls back to an external
        provider only when explicitly enabled in Provider Settings. Never used by Public Chat.
        / உள்ளூர் மாடல் இயக்கம் -- நிர்வாகிகளுக்கு மட்டும்.
      </p>

      {lrDiag && (
        <section className="metric-grid">
          <StatusCard
            label="Backend"
            value={lrDiag.local_available ? 'Local' : (lrDiag.external_fallback_enabled ? 'External' : 'Unavailable')}
            tone={lrDiag.local_available ? 'good' : (lrDiag.external_fallback_enabled ? 'neutral' : 'warn')}
          />
          <StatusCard label="llama-cpp-python installed" value={String(lrDiag.llama_cpp_installed)} tone={lrDiag.llama_cpp_installed ? 'good' : 'warn'} />
          <StatusCard label="Active sessions" value={lrDiag.active_session_count} tone="neutral" />
          <StatusCard label="Total messages" value={lrDiag.total_messages} tone="neutral" />
        </section>
      )}
      {lrDiag && !lrDiag.local_available && !lrDiag.external_fallback_enabled && (
        <div className="notice">
          No local model is configured and no external fallback is enabled -- the assistant will
          honestly report itself unavailable rather than fail silently. Configure a model under
          "Local Model Config" below, or enable an external provider in Provider Settings.
        </div>
      )}

      <div className="dataset-tabs">
        {lrSubTabs.map((t) => (
          <Button key={t} className={lrSubTab === t ? 'active' : ''} onClick={() => setLrSubTab(t)}>{t}</Button>
        ))}
      </div>

      {lrSubTab === 'Chat' && (
        <ChatPanel variant="full" admin={admin} toast={toast} />
      )}

      {lrSubTab === 'Explain Page' && (
        <form onSubmit={submitLrExplainPage} className="card">
          <label>Page ID</label>
          <input value={lrExplainPageForm.page_id} onChange={(e) => setLrExplainPageForm((prev) => ({ ...prev, page_id: e.target.value }))} placeholder="e.g. mini_brain" />
          <label>Nav Key</label>
          <input value={lrExplainPageForm.nav_key} onChange={(e) => setLrExplainPageForm((prev) => ({ ...prev, nav_key: e.target.value }))} placeholder="e.g. Brud Mini Brain" />
          <Button type="submit" disabled={lrBusy}>Explain this page</Button>
        </form>
      )}

      {lrSubTab === 'Summarize Report' && (
        <form onSubmit={submitLrSummarizeReport} className="card">
          <label>Report JSON</label>
          <textarea rows={6} value={lrReportForm} onChange={(e) => setLrReportForm(e.target.value)} />
          <Button type="submit" disabled={lrBusy}>Summarize current report</Button>
        </form>
      )}

      {lrSubTab === 'Summarize Regression' && (
        <form onSubmit={submitLrSummarizeRegression} className="card">
          <label>Regression Result JSON</label>
          <textarea rows={6} value={lrRegressionForm} onChange={(e) => setLrRegressionForm(e.target.value)} />
          <Button type="submit" disabled={lrBusy}>Summarize regression</Button>
        </form>
      )}

      {lrSubTab === 'Explain Error' && (
        <form onSubmit={submitLrExplainError} className="card">
          <label>Error message</label>
          <textarea rows={4} value={lrErrorForm} onChange={(e) => setLrErrorForm(e.target.value)} />
          <Button type="submit" disabled={lrBusy || !lrErrorForm.trim()}>Explain error</Button>
        </form>
      )}

      {lrSubTab === 'Next Actions' && (
        <>
          <form onSubmit={submitLrNextActions} className="card">
            <label>Status Snapshot JSON</label>
            <textarea rows={5} value={lrStatusSnapshotForm} onChange={(e) => setLrStatusSnapshotForm(e.target.value)} />
            <Button type="submit" disabled={lrBusy}>Next actions</Button>
          </form>
          {lrNextActionsResult && (
            <ul className="notice">
              {lrNextActionsResult.map((a, i) => (
                <li key={i}>[{a.severity}] {a.title} -- {a.reason}</li>
              ))}
            </ul>
          )}
        </>
      )}

      {lrSubTab === 'Local Model Config' && (
        <div className="card">
          <p className="notice">
            Saved via Provider Settings' generic <code>config</code> field (no new backend route --
            this reuses MB-27's existing <code>PATCH /providers/{'{id}'}</code>).
          </p>
          <label>Model path (must resolve inside the allowed model directory)</label>
          <input
            value={lrLocalModelConfig.model_path}
            onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, model_path: e.target.value }))}
            placeholder="e.g. qwen2.5-0.5b-instruct-q4_k_m.gguf"
          />
          <label>Context length</label>
          <input type="number" value={lrLocalModelConfig.context_length} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, context_length: e.target.value }))} />
          <label>Max tokens</label>
          <input type="number" value={lrLocalModelConfig.max_tokens} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, max_tokens: e.target.value }))} />
          <label>Temperature</label>
          <input type="number" step="0.05" value={lrLocalModelConfig.temperature} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, temperature: e.target.value }))} />
          <label>Threads</label>
          <input type="number" value={lrLocalModelConfig.threads} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, threads: e.target.value }))} />
          <Button disabled={lrBusy} onClick={saveLrLocalModelConfig}>Save</Button>
        </div>
      )}

      {lrSubTab === 'Diagnostics' && (
        <>
          {lrDiag && <pre className="notice">{JSON.stringify(lrDiag, null, 2)}</pre>}
          {!lrDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
