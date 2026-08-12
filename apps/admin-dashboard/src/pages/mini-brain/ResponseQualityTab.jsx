import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function ResponseQualityTab({ qDiagnostics, runQualityGenerate, qQuestion, setQQuestion, qBusy, qResult, qHistory }) {
  return (
    <>
      <p className="notice">
        MB-04B -- a Response Quality layer that runs entirely after generation, on already-produced
        text. No AI model, no embeddings, no vector search: every check below is deterministic
        string/script analysis. It sits on top of MB-04A's own prompt pipeline without changing it.
      </p>
      {qDiagnostics && (
        <section className="metric-grid">
          <StatusCard label="AI model used" value={String(qDiagnostics.ai_model_used)} tone={qDiagnostics.ai_model_used ? 'waiting' : 'good'} />
          <StatusCard label="Database tables" value={qDiagnostics.database_tables} tone="good" />
          <StatusCard label="Pipeline stages" value={qDiagnostics.pipeline_stages.length} tone="neutral" />
        </section>
      )}

      <form className="inline-form training-form" onSubmit={runQualityGenerate}>
        <label>Question<input value={qQuestion} onChange={(e) => setQQuestion(e.target.value)} placeholder="e.g. How does dataset duplicate detection work?" /></label>
        <Button type="submit" disabled={qBusy || !qQuestion}>{qBusy ? 'Generating + checking…' : 'Generate and check quality'}</Button>
      </form>

      {qResult && (
        <>
          <section className="metric-grid">
            <StatusCard label="Overall quality" value={qResult.quality.quality_score.overall_quality} tone={qResult.quality.quality_score.overall_quality >= 70 ? 'good' : qResult.quality.quality_score.overall_quality >= 40 ? 'neutral' : 'waiting'} />
            <StatusCard label="Echo score" value={qResult.quality.quality_score.echo_score} tone={qResult.quality.echo.severity === 'dominant' ? 'waiting' : qResult.quality.echo.severity === 'partial' ? 'neutral' : 'good'} />
            <StatusCard label="Language score" value={qResult.quality.quality_score.language_score} tone={qResult.quality.language.matches_expectation ? 'good' : 'waiting'} />
            <StatusCard label="Tamil score" value={qResult.quality.quality_score.tamil_score ?? 'n/a'} tone="neutral" />
            <StatusCard label="Formatting score" value={qResult.quality.quality_score.formatting_score} tone="neutral" />
            <StatusCard label="Consistency score" value={qResult.quality.quality_score.consistency_score} tone={qResult.quality.consistency.passed ? 'good' : 'waiting'} />
            <StatusCard label="Processing time" value={`${qResult.quality.processing_time_ms} ms`} tone="good" />
          </section>

          <h4>Echo detection</h4>
          <div className="notice">
            <p><strong>Detected:</strong> {String(qResult.quality.echo.echo_detected)} ({qResult.quality.echo.echo_type}, severity: {qResult.quality.echo.severity})</p>
            <p><strong>Overlap ratio:</strong> {qResult.quality.echo.overlap_ratio} ({qResult.quality.echo.overlap_length_chars} chars)</p>
            <p><strong>Matched labels:</strong> {qResult.quality.echo.matched_labels.join(', ') || 'none'}</p>
            <p><strong>Actions performed:</strong> {qResult.quality.actions_performed.join(', ') || 'none'}</p>
          </div>

          <h4>Language quality</h4>
          <div className="notice">
            <p><strong>Detected:</strong> {qResult.quality.language.language} → resolved <strong>{qResult.quality.language.resolved_output_language}</strong>, expected <strong>{qResult.quality.language.expected_output_language}</strong></p>
            <p><strong>Matches expectation:</strong> {String(qResult.quality.language.matches_expectation)}</p>
          </div>

          {qResult.quality.tamil_fluency && (
            <>
              <h4>Tamil quality (script-level only, not semantic grammar)</h4>
              <div className="notice">
                <p><strong>Passed:</strong> {String(qResult.quality.tamil_fluency.passed)}</p>
                <ul>{qResult.quality.tamil_fluency.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
                {!qResult.quality.tamil_fluency.issues.length && <p>No script-level issues found.</p>}
              </div>
            </>
          )}

          <h4>Formatting</h4>
          <div className="notice">
            <p><strong>Passed:</strong> {String(qResult.quality.formatting.passed)}</p>
            <ul>{qResult.quality.formatting.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
          </div>

          <h4>Consistency</h4>
          <div className="notice">
            <p><strong>Passed:</strong> {String(qResult.quality.consistency.passed)}</p>
            <ul>{qResult.quality.consistency.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
          </div>

          <h4>Final response (after quality cleanup)</h4>
          <div className="notice"><p>{qResult.final_response_text || <em>No substantive answer survived echo cleanup -- honestly reported, not fabricated.</em>}</p></div>
        </>
      )}

      <h4>Diagnostic history (this session only, not persisted)</h4>
      <div className="data-list">
        {qHistory.map((entry, i) => (
          <article key={i}>
            <strong>{entry.overall}</strong> — {entry.question}
            <div><small>{entry.at}</small></div>
          </article>
        ))}
        {!qHistory.length && <div className="notice">No quality checks run yet this session.</div>}
      </div>
    </>
  )
}
