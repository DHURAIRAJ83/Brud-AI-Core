import { useEffect, useState } from 'react'
import {
  promptCompare,
  promptGenerate,
  promptLanguageDetect,
  promptTemplates,
} from '../services/api.js'

const NOTICE = 'MB-04A: Prompt & Context Optimization -- a deterministic pipeline (language detection, template selection, context budgeting) that runs in front of whichever local or external model is currently loaded. The template used for a given question is always chosen automatically by the analyzed question, never picked by hand.'

function Pre({ value }) {
  if (!value) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

export default function PromptOptimizationPage() {
  const [question, setQuestion] = useState('')
  const [maxTokens, setMaxTokens] = useState(256)
  const [timeoutSeconds, setTimeoutSeconds] = useState(90)
  const [knowledgeBudgetChars, setKnowledgeBudgetChars] = useState(900)

  const [templates, setTemplates] = useState({})
  const [templatesLoaded, setTemplatesLoaded] = useState(false)
  const [templatesError, setTemplatesError] = useState('')

  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState('')
  const [detectResult, setDetectResult] = useState(null)

  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState('')
  const [generateResult, setGenerateResult] = useState(null)

  const [comparing, setComparing] = useState(false)
  const [compareError, setCompareError] = useState('')
  const [compareResult, setCompareResult] = useState(null)

  function loadTemplates() {
    setTemplatesLoaded(false)
    setTemplatesError('')
    promptTemplates()
      .then((data) => setTemplates(data.templates ?? {}))
      .catch((error) => setTemplatesError(error.message))
      .finally(() => setTemplatesLoaded(true))
  }

  useEffect(() => { loadTemplates() }, [])

  async function runDetect() {
    if (!question.trim() || detecting) return
    setDetecting(true)
    setDetectError('')
    try { setDetectResult(await promptLanguageDetect(question)) }
    catch (error) { setDetectError(error.message) }
    finally { setDetecting(false) }
  }

  async function runGenerate() {
    if (!question.trim() || generating) return
    setGenerating(true)
    setGenerateError('')
    setGenerateResult(null)
    try {
      setGenerateResult(await promptGenerate(question, { maxTokens, timeoutSeconds, knowledgeBudgetChars }))
    } catch (error) {
      setGenerateError(error.message)
    } finally {
      setGenerating(false)
    }
  }

  async function runCompare() {
    if (!question.trim() || comparing) return
    setComparing(true)
    setCompareError('')
    setCompareResult(null)
    try {
      setCompareResult(await promptCompare(question, { maxTokens, timeoutSeconds, knowledgeBudgetChars }))
    } catch (error) {
      setCompareError(error.message)
    } finally {
      setComparing(false)
    }
  }

  return (
    <>
      <div className="system-heading">
        <span>MB-04A</span>
        <h2>Prompt &amp; Context Optimization</h2>
        <p>{NOTICE}</p>
      </div>

      <form className="inline-form training-form" onSubmit={(event) => event.preventDefault()}>
        <label style={{ gridColumn: '1 / -1' }}>
          Question
          <textarea
            rows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What is pending review right now?"
          />
        </label>
        <label>Max tokens<input type="number" min="1" max="1024" value={maxTokens} onChange={(event) => setMaxTokens(Number(event.target.value))} /></label>
        <label>Timeout (seconds)<input type="number" min="1" max="300" value={timeoutSeconds} onChange={(event) => setTimeoutSeconds(Number(event.target.value))} /></label>
        <label>Knowledge budget (chars)<input type="number" min="100" max="4000" value={knowledgeBudgetChars} onChange={(event) => setKnowledgeBudgetChars(Number(event.target.value))} /></label>
        <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '10px' }}>
          <button type="button" onClick={runDetect} disabled={detecting || !question.trim()}>
            {detecting ? 'Detecting…' : 'Detect language'}
          </button>
          <button type="button" onClick={runGenerate} disabled={generating || !question.trim()}>
            {generating ? 'Generating…' : 'Generate optimized prompt'}
          </button>
          <button type="button" onClick={runCompare} disabled={comparing || !question.trim()}>
            {comparing ? 'Comparing…' : 'Compare baseline vs optimized'}
          </button>
        </div>
      </form>

      {detectError && <div className="form-error">{detectError}</div>}
      {detectResult && (
        <>
          <h3>Language detection</h3>
          <div className="metric-grid">
            <article className="status-card"><span>Detected language</span><strong>{detectResult.language}</strong></article>
            <article className="status-card"><span>Resolved output language</span><strong>{detectResult.resolved_output_language}</strong></article>
            <article className="status-card"><span>Tamil ratio</span><strong>{detectResult.tamil_ratio}</strong></article>
            <article className="status-card"><span>Effective Tamil ratio</span><strong>{detectResult.effective_tamil_ratio}</strong></article>
          </div>
        </>
      )}

      <h3>Available templates {templatesLoaded && !templatesError ? `(${Object.keys(templates).length})` : ''}</h3>
      <p className="notice">The pipeline auto-selects one of these based on the analyzed question -- there is no manual override in the backend, so none is offered here either.</p>
      {!templatesLoaded && <p className="notice">Loading templates…</p>}
      {templatesLoaded && templatesError && (
        <div className="notice error-notice">
          <strong>Unable to load templates</strong>
          <p>{templatesError}</p>
          <button type="button" onClick={loadTemplates}>Retry</button>
        </div>
      )}
      {templatesLoaded && !templatesError && (
        <div className="data-list">
          {Object.entries(templates).map(([category, instruction]) => (
            <article key={category}>
              <div><strong>{category}</strong></div>
              <small>{instruction}</small>
            </article>
          ))}
        </div>
      )}

      {generateError && <div className="form-error">{generateError}</div>}
      {generateResult && (
        <>
          <h3>Generated reply</h3>
          <p className="notice">Auto-selected template: <strong>{generateResult.template_category}</strong> · output language: <strong>{generateResult.output_language}</strong></p>
          <div className="metric-grid">
            <article className="status-card"><span>Prompt length (chars)</span><strong>{generateResult.prompt_length_chars}</strong></article>
            <article className="status-card"><span>Total seconds</span><strong>{generateResult.total_seconds}</strong></article>
            <article className="status-card"><span>Validation passed</span><strong>{String(generateResult.validation.passed)}</strong></article>
            <article className="status-card"><span>Rebuilt for language mismatch</span><strong>{String(generateResult.rebuilt)}</strong></article>
          </div>
          <Pre value={generateResult.response} />
        </>
      )}

      {compareError && <div className="form-error">{compareError}</div>}
      {compareResult && (
        <>
          <h3>Baseline vs optimized</h3>
          <p className="notice">Auto-selected template: <strong>{compareResult.template_category}</strong> · output language: <strong>{compareResult.output_language}</strong></p>
          <div className="training-grid">
            <section className="training-detail">
              <h3>Baseline (unmodified prompt)</h3>
              <div className="metric-grid">
                <article className="status-card"><span>Prompt length (chars)</span><strong>{compareResult.baseline.prompt_length_chars}</strong></article>
                <article className="status-card"><span>Response length (chars)</span><strong>{compareResult.baseline.response_length_chars}</strong></article>
                <article className="status-card"><span>Seconds</span><strong>{compareResult.baseline.seconds}</strong></article>
                <article className="status-card"><span>Validation passed</span><strong>{String(compareResult.baseline.validation.passed)}</strong></article>
              </div>
              <Pre value={compareResult.baseline.response} />
            </section>
            <section className="training-detail">
              <h3>Optimized (MB-04A)</h3>
              <div className="metric-grid">
                <article className="status-card"><span>Prompt length (chars)</span><strong>{compareResult.optimized.prompt_length_chars}</strong></article>
                <article className="status-card"><span>Response length (chars)</span><strong>{compareResult.optimized.response_length_chars}</strong></article>
                <article className="status-card"><span>Seconds</span><strong>{compareResult.optimized.seconds}</strong></article>
                <article className="status-card"><span>Validation passed</span><strong>{String(compareResult.optimized.validation.passed)}</strong></article>
              </div>
              <Pre value={compareResult.optimized.response} />
            </section>
          </div>
        </>
      )}
    </>
  )
}
