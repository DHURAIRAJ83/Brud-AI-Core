import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function RuntimeTab({
  rtStatus, rtStats, rtBusy, rtModels, runRuntimeAction,
  rtRegisterForm, setRtRegisterForm, submitRegisterModel,
  rtDiagnostics,
}) {
  return (
    <>
      <p className="notice">
        MB-04 -- CPU-only local runtime, GGUF via a lightweight backend, never Ollama, never
        Docker. No model is currently loaded in this environment: <code>llama-cpp-python</code>{' '}
        is not installed and no <code>.gguf</code> file is provisioned. The full Model Manager
        below is real and working against that honest state.
      </p>
      {rtStatus && rtStats ? (
        <section className="metric-grid">
          <StatusCard label="Runtime status" value={rtStatus.state} tone={rtStatus?.state === 'loaded' ? 'good' : rtStatus?.state === 'error' ? 'waiting' : 'neutral'} />
          <StatusCard label="Current model" value={rtStatus.current_model?.name ?? 'none'} tone="neutral" />
          <StatusCard label="Model version" value={rtStatus.current_model?.quantization ?? 'n/a'} tone="neutral" />
          <StatusCard label="Context size" value={rtStatus.current_model?.context_length ?? 'n/a'} tone="neutral" />
          <StatusCard label="Load time" value={`${rtStats.last_load_time_ms ?? 'n/a'} ms`} tone="neutral" />
          <StatusCard label="Response time" value={`${rtStats.last_response_time_ms ?? 'n/a'} ms`} tone="neutral" />
          <StatusCard label="Available memory" value={`${Math.round(rtStats.available_memory_bytes / 1048576)} MB`} tone="neutral" />
          <StatusCard label="Process CPU time" value={`${rtStats.process_cpu_time_seconds}s`} tone="neutral" />
          <StatusCard label="Process peak memory" value={`${Math.round(rtStats.process_max_rss_kb / 1024)} MB`} tone="neutral" />
        </section>
      ) : (
        <Skeleton lines={3} />
      )}

      <div className="form-row">
        <Button onClick={() => runRuntimeAction('load')} disabled={rtBusy || !rtModels.length}>Load</Button>
        <Button onClick={() => runRuntimeAction('unload')} disabled={rtBusy}>Unload</Button>
        <Button onClick={() => runRuntimeAction('reload')} disabled={rtBusy}>Reload</Button>
      </div>
      {rtStatus?.last_error && <div className="form-error" role="alert">{rtStatus.last_error}</div>}

      <h4>Register a model</h4>
      <form className="inline-form training-form" onSubmit={submitRegisterModel}>
        <label>Name<input value={rtRegisterForm.name} onChange={(e) => setRtRegisterForm((p) => ({ ...p, name: e.target.value }))} /></label>
        <label>Path<input value={rtRegisterForm.path} onChange={(e) => setRtRegisterForm((p) => ({ ...p, path: e.target.value }))} placeholder="/path/to/model.gguf" /></label>
        <label>Quantization<input value={rtRegisterForm.quantization} onChange={(e) => setRtRegisterForm((p) => ({ ...p, quantization: e.target.value }))} /></label>
        <label>Context length<input type="number" value={rtRegisterForm.context_length} onChange={(e) => setRtRegisterForm((p) => ({ ...p, context_length: Number(e.target.value) }))} /></label>
        <Button type="submit">Register</Button>
      </form>

      <h4>Registered models</h4>
      <div className="data-list">
        {rtModels.map((m) => (
          <article key={m.public_id}>
            <strong>{m.name}</strong> — {m.quantization} — {m.context_length} tokens
            <div><small>{m.path}</small></div>
          </article>
        ))}
        {!rtModels.length && <div className="notice">No models registered yet.</div>}
      </div>

      <h4>Diagnostics</h4>
      {rtDiagnostics && (
        <section className="metric-grid">
          <StatusCard label="Registered models" value={rtDiagnostics.registered_model_count} tone="neutral" />
          <StatusCard label="Total generations" value={rtDiagnostics.statistics.total_generations} tone="neutral" />
          <StatusCard label="Health" value={rtDiagnostics.health.status} tone={rtDiagnostics.health.status === 'healthy' ? 'good' : rtDiagnostics.health.status === 'unhealthy' ? 'waiting' : 'neutral'} />
          <StatusCard label="Memory measurement" value={rtDiagnostics.statistics.memory_measurement} tone="neutral" />
        </section>
      )}
    </>
  )
}
