import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function IntelligenceEngineTab({ runIntelligenceAnalysis, ieQuestion, setIeQuestion, ieBusy, ieResult }) {
  return (
    <>
      <p className="notice">
        MB-03 -- a deterministic decision engine, not a language model. Every field below
        traces to a keyword match or a fixed rule; nothing is generated or guessed.
      </p>
      <form className="inline-form training-form" onSubmit={runIntelligenceAnalysis}>
        <label>Question<input value={ieQuestion} onChange={(e) => setIeQuestion(e.target.value)} placeholder="e.g. How do I train the tokenizer?" /></label>
        <Button type="submit" disabled={ieBusy || !ieQuestion}>{ieBusy ? 'Analyzing…' : 'Analyze'}</Button>
      </form>

      {ieResult && (
        <>
          <section className="metric-grid">
            <StatusCard label="Intent" value={ieResult.question_analysis.intent} tone="neutral" />
            <StatusCard label="Question type" value={ieResult.question_analysis.question_type} tone="neutral" />
            <StatusCard label="Response type" value={ieResult.response_plan.suggested_response_type} tone="neutral" />
            <StatusCard label="Confidence" value={`${ieResult.confidence.score} (${ieResult.confidence.band})`} tone={ieResult.confidence.band === 'high' ? 'good' : ieResult.confidence.band === 'none' ? 'waiting' : 'neutral'} />
            <StatusCard label="Processing time" value={`${ieResult.diagnostics.processing_time_ms} ms`} tone="neutral" />
            <StatusCard label="Candidates scanned" value={ieResult.diagnostics.candidate_item_count} tone="neutral" />
          </section>

          <h4>Knowledge</h4>
          <div className="notice">
            <p><strong>Primary:</strong> {ieResult.knowledge_plan.primary_knowledge.join(', ') || '--'}</p>
            <p><strong>Supporting:</strong> {ieResult.knowledge_plan.supporting_knowledge.join(', ') || '--'}</p>
            <p><strong>Optional:</strong> {ieResult.knowledge_plan.optional_knowledge.join(', ') || '--'}</p>
            <p><strong>Excluded:</strong> {ieResult.knowledge_plan.excluded_knowledge.join(', ') || '--'}</p>
          </div>

          <h4>Workflow</h4>
          <div className="notice">
            <p><strong>Current step:</strong> {ieResult.workflow.current_step || '--'}</p>
            <p><strong>Previous:</strong> {ieResult.workflow.previous_steps.join(', ') || '--'}</p>
            <p><strong>Next:</strong> {ieResult.workflow.next_steps.join(', ') || '--'}</p>
            <p><strong>Dependencies:</strong> {ieResult.workflow.dependencies.join(', ') || '--'}</p>
          </div>

          <h4>Context</h4>
          <div className="notice">
            <p><strong>Matched items:</strong> {ieResult.context.matched_item_titles.join(', ') || '--'}</p>
            <p><strong>Documentation:</strong> {ieResult.context.documentation_references.join(', ') || '--'}</p>
          </div>

          <h4>Features</h4>
          <div className="notice">
            <p><strong>Dashboard pages:</strong> {ieResult.features.dashboard_pages.join(', ') || '--'}</p>
            <p><strong>Backend services:</strong> {ieResult.features.backend_services.join(', ') || '--'}</p>
            <p><strong>APIs:</strong> {ieResult.features.apis.join(', ') || '--'}</p>
          </div>

          <h4>Response plan (for a future model -- not a final answer)</h4>
          <pre className="notice">{JSON.stringify(ieResult.response_plan, null, 2)}</pre>

          <h4>Rules applied</h4>
          <div className="notice">
            <p><strong>Flags:</strong> {ieResult.rules.flags.join(', ') || 'none'}</p>
            <ul>{ieResult.rules.disclaimers.map((d) => <li key={d}>{d}</li>)}</ul>
          </div>

          <h4>Confidence breakdown</h4>
          <table>
            <thead><tr><th>Reason</th><th>Points</th></tr></thead>
            <tbody>
              {ieResult.confidence.contributions.map((c) => (
                <tr key={c.reason}><td>{c.reason}</td><td>{c.points}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  )
}
