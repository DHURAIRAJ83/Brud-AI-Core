import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const rmSubTabs = [
  'Overview', 'Catalog', 'Installed', 'Download', 'Load / Unload', 'Benchmark',
  'Performance', 'Diagnostics', 'Events', 'History',
]

export default function RuntimeManagerTab({
  rmStatusData, rmHardwareData,
  rmSubTab, setRmSubTab,
  rmBusy, installRecommendedModel,
  rmCatalogData, setRmSelectedModelId,
  rmInstalledList, runRmRemove,
  rmSelectedModelId, runRmDownload, runRmVerify, runRmInstallSelected, rmLastActionResult,
  rmLoadForm, setRmLoadForm, runRmLoad, runRmUnload,
  rmBenchmarkPrompt, setRmBenchmarkPrompt, runRmBenchmark, rmLastBenchmarkResult,
  loadRmEvents, rmEventsList,
  loadRmHistory, rmMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-30 -- Production Runtime Manager &amp; One-Click Local Model Lifecycle. Install, load,
        benchmark, and manage local GGUF models -- CPU-only, no GPU dependency, nothing downloads
        without an explicit click. / உள்ளூர் GGUF மாடல்களை நிறுவவும், ஏற்றவும், சோதிக்கவும் --
        வெளிப்படையான கிளிக் இல்லாமல் எதுவும் பதிவிறக்கப்படாது.
      </p>

      {rmStatusData && (
        <section className="metric-grid">
          <StatusCard label="Runtime" value={rmStatusData.loaded ? 'Loaded' : 'Not loaded'} tone={rmStatusData.loaded ? 'good' : 'neutral'} />
          <StatusCard label="Installed models" value={rmStatusData.installed_count} tone="neutral" />
          <StatusCard label="RAM tier" value={rmHardwareData?.recommended_ram_tier} tone="neutral" />
          <StatusCard label="Disk free" value={rmHardwareData ? `${rmHardwareData.disk_free_gb} GB` : '—'} tone="neutral" />
        </section>
      )}

      <div className="dataset-tabs">
        {rmSubTabs.map((t) => (
          <Button key={t} className={rmSubTab === t ? 'active' : ''} onClick={() => setRmSubTab(t)}>{t}</Button>
        ))}
      </div>

      {rmSubTab === 'Overview' && (
        <div className="card">
          <Button disabled={rmBusy} onClick={installRecommendedModel}>Install Recommended Model / பரிந்துரைக்கப்பட்ட மாடலை நிறுவவும்</Button>
          {rmStatusData?.current_model && (
            <pre className="notice">{JSON.stringify(rmStatusData.current_model, null, 2)}</pre>
          )}
        </div>
      )}

      {rmSubTab === 'Catalog' && (
        <table>
          <thead><tr><th>Model</th><th>Tier</th><th>RAM (GB)</th><th>Tamil</th><th /></tr></thead>
          <tbody>
            {rmCatalogData.map((m) => (
              <tr key={m.model_id}>
                <td>{m.display_name}</td><td>{m.tier}</td><td>{m.recommended_ram_gb}</td><td>{m.tamil_support}</td>
                <td><Button onClick={() => setRmSelectedModelId(m.model_id)}>Select</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {rmSubTab === 'Installed' && (
        <table>
          <thead><tr><th>Model</th><th>Status</th><th>Size</th><th /></tr></thead>
          <tbody>
            {rmInstalledList.map((m) => (
              <tr key={m.public_id}>
                <td>{m.model_name}</td><td>{m.status}</td><td>{m.file_size_bytes ? Math.round(m.file_size_bytes / (1024*1024)) + ' MB' : '—'}</td>
                <td><Button disabled={rmBusy} onClick={() => runRmRemove(m.model_name)}>Remove</Button></td>
              </tr>
            ))}
            {!rmInstalledList.length && <tr><td colSpan={4}>No models installed yet.</td></tr>}
          </tbody>
        </table>
      )}

      {rmSubTab === 'Download' && (
        <div className="card">
          <label>Model ID</label>
          <input value={rmSelectedModelId} onChange={(e) => setRmSelectedModelId(e.target.value)} placeholder="e.g. qwen2.5-1.5b-instruct-q4_k_m" />
          <div>
            <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmDownload}>Download</Button>
            <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmVerify}>Verify</Button>
            <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmInstallSelected}>Install</Button>
          </div>
          {rmLastActionResult && <pre className="notice">{JSON.stringify(rmLastActionResult, null, 2)}</pre>}
        </div>
      )}

      {rmSubTab === 'Load / Unload' && (
        <div className="card">
          <label>Context length</label>
          <input type="number" value={rmLoadForm.context_length} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, context_length: e.target.value }))} />
          <label>Max tokens</label>
          <input type="number" value={rmLoadForm.max_tokens} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, max_tokens: e.target.value }))} />
          <label>Temperature</label>
          <input type="number" step="0.05" value={rmLoadForm.temperature} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, temperature: e.target.value }))} />
          <label>Threads</label>
          <input type="number" value={rmLoadForm.threads} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, threads: e.target.value }))} />
          <div>
            <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmLoad}>Load</Button>
            <Button disabled={rmBusy} onClick={runRmUnload}>Unload</Button>
          </div>
        </div>
      )}

      {rmSubTab === 'Benchmark' && (
        <div className="card">
          <label>Prompt</label>
          <textarea rows={2} value={rmBenchmarkPrompt} onChange={(e) => setRmBenchmarkPrompt(e.target.value)} />
          <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmBenchmark}>Run Benchmark</Button>
          {rmLastBenchmarkResult && (
            <div className="notice">
              Rating: {rmLastBenchmarkResult.rating_label?.en} / {rmLastBenchmarkResult.rating_label?.ta} --
              {' '}{rmLastBenchmarkResult.tokens_per_second} tok/s -- {rmLastBenchmarkResult.peak_ram_mb} MB peak RAM
            </div>
          )}
        </div>
      )}

      {rmSubTab === 'Performance' && (
        <>
          {rmLastBenchmarkResult && <pre className="notice">{JSON.stringify(rmLastBenchmarkResult, null, 2)}</pre>}
          {!rmLastBenchmarkResult && <p className="notice">Run a benchmark to see performance data.</p>}
        </>
      )}

      {rmSubTab === 'Diagnostics' && (
        <>
          {rmHardwareData && <pre className="notice">{JSON.stringify(rmHardwareData, null, 2)}</pre>}
          {!rmHardwareData && <Skeleton lines={2} />}
        </>
      )}

      {rmSubTab === 'Events' && (
        <>
          <Button disabled={rmBusy} onClick={loadRmEvents}>Load events</Button>
          <ul className="notice">
            {rmEventsList.map((e) => (
              <li key={e.public_id}>{e.created_at} -- {e.model_name || 'n/a'} -- {e.event_type}</li>
            ))}
            {!rmEventsList.length && <li>No events loaded yet.</li>}
          </ul>
        </>
      )}

      {rmSubTab === 'History' && (
        <>
          <Button disabled={rmBusy} onClick={loadRmHistory}>Load history</Button>
          <ul className="notice">
            {rmMemoryList.map((m) => (
              <li key={m.public_id}>{m.created_at} -- {m.model_name || 'n/a'} -- {m.event_type}</li>
            ))}
            {!rmMemoryList.length && <li>No history loaded yet.</li>}
          </ul>
        </>
      )}
    </>
  )
}
