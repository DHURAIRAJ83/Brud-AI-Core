import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function CapabilityTab({ capDiagnostics, runCapabilityGenerate, capQuestion, setCapQuestion, capBusy, capResult }) {
  return (
    <>
      <p className="notice">
        MB-04C -- optimizes HOW the existing CPU model is used: strategy selection, output-length
        checking, and a single bounded retry. No new model, no new runtime, no new prompt builder --
        this reuses MB-04A's prompt and MB-04's Runtime exactly as they already are.
      </p>
      {capDiagnostics && (
        <section className="metric-grid">
          <StatusCard label="AI model used" value={String(capDiagnostics.ai_model_used)} tone={capDiagnostics.ai_model_used ? 'waiting' : 'good'} />
          <StatusCard label="Max retries" value={capDiagnostics.max_retries} tone="good" />
          <StatusCard label="Known profiles" value={capDiagnostics.known_profiles.length} tone="neutral" />
        </section>
      )}

      <form className="inline-form training-form" onSubmit={runCapabilityGenerate}>
        <label>Question<input value={capQuestion} onChange={(e) => setCapQuestion(e.target.value)} placeholder="e.g. How does dataset duplicate detection work?" /></label>
        <Button type="submit" disabled={capBusy || !capQuestion}>{capBusy ? 'Generating…' : 'Generate with capability optimization'}</Button>
      </form>

      {capResult && (
        <>
          <section className="metric-grid">
            <StatusCard label="Current model" value={capResult.profile.display_name} tone={capResult.profile.verified ? 'good' : 'waiting'} />
            <StatusCard label="Category" value={capResult.category} tone="neutral" />
            <StatusCard label="Strategy" value={capResult.strategy.name} tone="neutral" />
            <StatusCard label="Retry" value={capResult.retry.attempted ? capResult.retry.decision.reason : 'not needed'} tone={capResult.retry.attempted ? 'waiting' : 'good'} />
            <StatusCard label="Output length" value={`${capResult.output_length.word_count} words`} tone={capResult.output_length.issues.length ? 'waiting' : 'good'} />
            <StatusCard label="Generation time" value={`${Math.round(capResult.generation_time_ms)} ms`} tone="neutral" />
          </section>

          <h4>Capability Profile</h4>
          <div className="notice">
            <p><strong>Verified:</strong> {String(capResult.profile.verified)} — <em>{capResult.profile.source}</em></p>
            <p><strong>Reasoning quality:</strong> {capResult.profile.reasoning_quality} · <strong>Coding quality:</strong> {capResult.profile.coding_quality}</p>
            <p><strong>Max tokens used:</strong> {capResult.max_tokens_used} (ceiling: {capResult.profile.response_limits.max_tokens_ceiling})</p>
          </div>

          {capResult.stability && (
            <>
              <h4>Stability (first vs retry)</h4>
              <div className="notice">
                <p><strong>Passed:</strong> {String(capResult.stability.passed)}</p>
                <ul>{capResult.stability.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
              </div>
            </>
          )}

          <h4>Warnings</h4>
          <div className="notice">
            <ul>{capResult.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            {!capResult.warnings.length && <p>No warnings.</p>}
          </div>

          <h4>Final response</h4>
          <div className="notice"><p>{capResult.response.text}</p></div>
        </>
      )}
    </>
  )
}
