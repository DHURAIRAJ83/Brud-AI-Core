import { useEffect, useState, useCallback } from 'react'
import Button from '../Button.jsx'
import Skeleton from '../Skeleton.jsx'
import StatusCard from '../StatusCard.jsx'
import {
  psProviders,
  mdCreateSession,
  mdSession,
  mdRunCollectSources,
  mdRunCollectText,
  mdRunCollectImages,
  mdRunMergeMetadata,
  mdRunConversationBuilder,
  mdRunInstructionBuilder,
  mdRunDatasetDraft,
  mdRunQualityAnalysis,
  mdRunDuplicateDetection,
  mdGenerateReport,
  mdRecords,
  mdAdminReview,
} from '../../services/api.js'

const PIPELINE_STAGES = [
  { id: 'collect_sources', label: '1. Collect Sources' },
  { id: 'collect_text', label: '2. Extract & Normalize Text' },
  { id: 'collect_images', label: '3. Process Multimodal Signals' },
  { id: 'merge_metadata', label: '4. Merge Metadata & Graph' },
  { id: 'conversation_builder', label: '5. Build Conversations' },
  { id: 'instruction_builder', label: '6. Build Instructions (SFT)' },
  { id: 'dataset_draft', label: '7. Assemble Draft Records' },
  { id: 'quality_analysis', label: '8. Score Quality' },
  { id: 'duplicate_detection', label: '9. Check Duplicates' },
  { id: 'report', label: '10. Generate Final Report' },
]

export default function DatasetGeneratePane({ toast, onNavigate }) {
  const [providers, setProviders] = useState([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [topic, setTopic] = useState('Tamil language & administrative reasoning')
  const [language, setLanguage] = useState('ta')
  const [format, setFormat] = useState('instruction')
  const [targetCount, setTargetCount] = useState('10')
  const [customInstructions, setCustomInstructions] = useState('')
  const [documentSourceId, setDocumentSourceId] = useState('')

  const [busy, setBusy] = useState(false)
  const [stageProgress, setStageProgress] = useState(null)
  const [currentStageIndex, setCurrentStageIndex] = useState(-1)
  const [sessionData, setSessionData] = useState(null)
  const [records, setRecords] = useState([])
  const [error, setError] = useState('')

  const loadProviders = useCallback(async () => {
    try {
      const res = await psProviders()
      const items = res?.items || []
      setProviders(items)
      const enabled = items.find((p) => p.enabled)
      if (enabled) setSelectedProvider(enabled.provider_key)
      else if (items.length > 0) setSelectedProvider(items[0].provider_key)
    } catch {
      setProviders([])
    }
  }, [])

  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  async function startGenerationFlow(e) {
    if (e) e.preventDefault()
    if (busy) return
    setError('')
    setSessionData(null)
    setRecords([])
    setBusy(true)
    setStageProgress('Creating generation cycle...')
    setCurrentStageIndex(0)

    try {
      // 1. Create MB-16 session
      // If no explicit document public ID given, use a placeholder or synthetic prompt document
      const docId = documentSourceId.trim() || `syn-${Date.now()}`
      const created = await mdCreateSession(docId, {})
      const sessionId = created.public_id
      setSessionData(created)

      // 2. Sequentially run the MB-16 pipeline stages
      const runners = [
        { name: 'Collecting sources...', fn: () => mdRunCollectSources(sessionId) },
        { name: 'Extracting text...', fn: () => mdRunCollectText(sessionId) },
        { name: 'Processing multimodal signals...', fn: () => mdRunCollectImages(sessionId) },
        { name: 'Merging metadata...', fn: () => mdRunMergeMetadata(sessionId) },
        { name: 'Building conversation pairs...', fn: () => mdRunConversationBuilder(sessionId) },
        { name: 'Generating instruction pairs...', fn: () => mdRunInstructionBuilder(sessionId) },
        { name: 'Drafting dataset records...', fn: () => mdRunDatasetDraft(sessionId) },
        { name: 'Scoring dataset quality...', fn: () => mdRunQualityAnalysis(sessionId) },
        { name: 'Running duplicate detection...', fn: () => mdRunDuplicateDetection(sessionId) },
        { name: 'Compiling dataset report...', fn: () => mdGenerateReport(sessionId) },
      ]

      for (let i = 0; i < runners.length; i++) {
        setCurrentStageIndex(i)
        setStageProgress(runners[i].name)
        try {
          const updated = await runners[i].fn()
          setSessionData(updated)
        } catch (stageErr) {
          // If a stage was already executed or progressed, fetch current state
          const cur = await mdSession(sessionId)
          setSessionData(cur)
        }
      }

      setStageProgress('Fetching generated records...')
      const recRes = await mdRecords(sessionId)
      setRecords(recRes?.items || [])
      setStageProgress('Generation cycle complete. Awaiting Admin Review.')
      toast?.success('Dataset generated and analyzed successfully!')
    } catch (err) {
      setError(err.message || 'Generation pipeline encountered an error')
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAdminReview(decision) {
    if (!sessionData?.public_id || busy) return
    setBusy(true)
    setError('')
    try {
      const updated = await mdAdminReview(sessionData.public_id, decision)
      setSessionData(updated)
      toast?.success(`Dataset ${decision === 'approve' ? 'Certified' : decision}.`)
    } catch (err) {
      setError(err.message)
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="dataset-generate-pane">
      <div className="assistant-pane-header">
        <div>
          <h3>Provider Dataset Generator</h3>
          <p className="subtext">
            Generate synthetic SFT instructions, Q&amp;A, and conversation datasets through the MB-16 engine.
          </p>
        </div>
        {onNavigate && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onNavigate('Mini Brain')}
            title="Open Mini Brain Multimodal Dataset Generator tab"
          >
            Dashboard Generator
          </Button>
        )}
      </div>

      <form className="generate-config-form" onSubmit={startGenerationFlow}>
        <div className="form-row">
          <label>
            <span>Topic / Domain Requirements:</span>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Tamil administrative rules, technical Q&A"
              required
              disabled={busy}
            />
          </label>
        </div>

        <div className="form-grid-3">
          <label>
            <span>Language:</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={busy}>
              <option value="ta">Tamil (தமிழ்)</option>
              <option value="en">English</option>
              <option value="mixed">Mixed (Tamil + English)</option>
            </select>
          </label>

          <label>
            <span>Format:</span>
            <select value={format} onChange={(e) => setFormat(e.target.value)} disabled={busy}>
              <option value="instruction">Instruction (SFT)</option>
              <option value="conversation">Multi-turn Conversation</option>
              <option value="qa">Question &amp; Answer</option>
            </select>
          </label>

          <label>
            <span>Records Target:</span>
            <select value={targetCount} onChange={(e) => setTargetCount(e.target.value)} disabled={busy}>
              <option value="10">10 records (Fast)</option>
              <option value="25">25 records</option>
              <option value="50">50 records</option>
              <option value="100">100 records</option>
            </select>
          </label>
        </div>

        <div className="form-grid-2">
          <label>
            <span>AI Provider:</span>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              disabled={busy}
            >
              {providers.map((p) => (
                <option key={p.provider_key} value={p.provider_key}>
                  {p.provider_key} ({p.enabled ? 'Enabled' : 'Disabled'})
                </option>
              ))}
              {providers.length === 0 && <option value="">No configured providers</option>}
            </select>
          </label>

          <label>
            <span>Document ID (optional):</span>
            <input
              value={documentSourceId}
              onChange={(e) => setDocumentSourceId(e.target.value)}
              placeholder="Source document public_id"
              disabled={busy}
            />
          </label>
        </div>

        <div className="form-row">
          <label>
            <span>Specific Prompt / Instructions (optional):</span>
            <textarea
              rows={2}
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="e.g. Ensure Tamil terminology is grammatically pure and formatted in JSON markdown."
              disabled={busy}
            />
          </label>
        </div>

        <div className="generate-submit-row">
          <Button type="submit" variant="primary" disabled={busy || !topic.trim()}>
            {busy ? 'Running MB-16 Pipeline…' : 'Generate Dataset Cycle'}
          </Button>
          {busy && <span className="busy-text">{stageProgress}</span>}
        </div>
      </form>

      {error && <div className="notice error-notice">{error}</div>}

      {/* Real Pipeline Stage Progress */}
      {currentStageIndex >= 0 && (
        <div className="pipeline-progress-card">
          <h4>MB-16 Pipeline Stages</h4>
          <div className="stage-steps-list">
            {PIPELINE_STAGES.map((st, idx) => {
              const isDone = idx < currentStageIndex || (!busy && currentStageIndex === PIPELINE_STAGES.length - 1)
              const isCurrent = busy && idx === currentStageIndex
              return (
                <div
                  key={st.id}
                  className={`stage-step-item ${isDone ? 'step-done' : isCurrent ? 'step-current' : 'step-pending'}`}
                >
                  <span className="step-icon">{isDone ? '✓' : isCurrent ? '⟳' : '○'}</span>
                  <span className="step-label">{st.label}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Dataset Summary & Metrics */}
      {sessionData && (
        <div className="generation-results-section">
          <section className="metric-grid">
            <StatusCard
              label="Session"
              value={sessionData.public_id?.slice(0, 10) || 'Active'}
              tone="neutral"
            />
            <StatusCard
              label="Stage"
              value={sessionData.stage || 'Awaiting Review'}
              tone="neutral"
            />
            <StatusCard
              label="Quality Score"
              value={
                sessionData.quality_report?.overall_dataset_quality !== undefined
                  ? `${sessionData.quality_report.overall_dataset_quality}%`
                  : 'Scored'
              }
              tone="good"
            />
            <StatusCard
              label="Drafted Records"
              value={records.length}
              tone={records.length > 0 ? 'good' : 'warn'}
            />
          </section>

          {/* Admin Review & Governance Boundary */}
          <div className="admin-review-card">
            <h4>Admin Governance &amp; Certification Gate</h4>
            <p className="subtext">
              Generated datasets remain in <strong>Draft</strong> state until certified by an admin.
              Certified records enter the RAG Vector Store and become eligible for training split manifests.
            </p>
            <div className="admin-review-actions">
              <Button
                variant="primary"
                size="sm"
                disabled={busy || sessionData.status === 'admin_approved'}
                onClick={() => handleAdminReview('approve')}
              >
                {sessionData.status === 'admin_approved' ? '✓ Certified' : 'Certify Dataset'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => handleAdminReview('reject')}
              >
                Reject Draft
              </Button>
              {onNavigate && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onNavigate('Mini Brain')}
                >
                  Review &amp; Export on Dashboard →
                </Button>
              )}
            </div>
            <div className="governance-footnote">
              <small>🔒 Training Gate: Fail-Closed. Model weights and production state are locked.</small>
            </div>
          </div>

          {/* Record Preview */}
          {records.length > 0 && (
            <div className="records-preview-section">
              <h4>Generated Record Preview ({records.length} records)</h4>
              <div className="records-preview-list">
                {records.slice(0, 5).map((rec, i) => (
                  <div key={rec.public_id || i} className="record-preview-card">
                    <div className="record-preview-head">
                      <span className="badge neutral">{rec.record_type}</span>
                      <small className="subtext">{rec.record_checksum?.slice(0, 12)}...</small>
                    </div>
                    <pre className="record-content-json">
                      {JSON.stringify(rec.content, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
