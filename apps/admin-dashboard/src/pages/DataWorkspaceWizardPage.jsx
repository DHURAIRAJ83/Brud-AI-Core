import { useCallback, useEffect, useState } from 'react'
import Button from '../components/Button.jsx'
import { useToast } from '../components/Toast.jsx'
import UploadStep from './wizard/UploadStep.jsx'
import OcrStep from './wizard/OcrStep.jsx'
import CleanStep from './wizard/CleanStep.jsx'
import ChunkStep from './wizard/ChunkStep.jsx'
import AiReviewStudioStep from './wizard/AiReviewStudioStep.jsx'
import ApproveStep from './wizard/ApproveStep.jsx'
import BuildRagStep from './wizard/BuildRagStep.jsx'

export const STEPS = [
  { key: 'upload', label: 'Upload', Component: UploadStep },
  { key: 'ocr', label: 'OCR', Component: OcrStep },
  { key: 'clean', label: 'Clean', Component: CleanStep },
  { key: 'chunk', label: 'Chunk', Component: ChunkStep },
  { key: 'review', label: 'AI Review Studio', Component: AiReviewStudioStep },
  { key: 'approve', label: 'Approve', Component: ApproveStep },
  { key: 'build_rag', label: 'Build RAG', Component: BuildRagStep },
]

const SCHEMA_VERSION = 1
const PAGE_NAME = 'Data Workspace Wizard'

function stepKeyFromHash() {
  const queryIndex = window.location.hash.indexOf('?')
  if (queryIndex === -1) return STEPS[0].key
  const requested = new URLSearchParams(window.location.hash.slice(queryIndex + 1)).get('step')
  return STEPS.some((candidate) => candidate.key === requested) ? requested : STEPS[0].key
}

function documentIdFromHash() {
  const queryIndex = window.location.hash.indexOf('?')
  if (queryIndex === -1) return null
  return new URLSearchParams(window.location.hash.slice(queryIndex + 1)).get('document') || null
}

function storageKey(documentId) {
  return `brud-admin:wizard:${documentId}`
}

function readStoredProgress(documentId) {
  if (!documentId) return null
  try {
    const raw = sessionStorage.getItem(storageKey(documentId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || parsed.version !== SCHEMA_VERSION) return null
    return parsed
  } catch {
    return null
  }
}

function writeStoredProgress(documentId, completedSteps) {
  if (!documentId) return
  try {
    sessionStorage.setItem(storageKey(documentId), JSON.stringify({ version: SCHEMA_VERSION, completedSteps }))
  } catch {
    // Ignore write failures (quota exceeded, disabled storage) -- the
    // in-memory wizard state still works for the rest of this session.
  }
}

export default function DataWorkspaceWizardPage({ onNavigate }) {
  const toast = useToast()
  const [documentId, setDocumentIdState] = useState(documentIdFromHash)
  const [documentTitle, setDocumentTitle] = useState('')
  const [step, setStepState] = useState(stepKeyFromHash)
  const [completedSteps, setCompletedSteps] = useState(() => readStoredProgress(documentIdFromHash())?.completedSteps ?? {})

  useEffect(() => {
    const pageName = window.location.hash.slice(1).split('?')[0] || PAGE_NAME
    const params = new URLSearchParams()
    params.set('step', step)
    if (documentId) params.set('document', documentId)
    window.history.replaceState(null, '', `#${pageName}?${params.toString()}`)
  }, [step, documentId])

  useEffect(() => {
    writeStoredProgress(documentId, completedSteps)
  }, [documentId, completedSteps])

  const currentIndex = STEPS.findIndex((candidate) => candidate.key === step)

  const stepUnlocked = useCallback((index) => {
    if (index === 0) return true
    return Boolean(completedSteps[STEPS[index - 1].key])
  }, [completedSteps])

  function goToStep(key) {
    const index = STEPS.findIndex((candidate) => candidate.key === key)
    if (index === -1 || !stepUnlocked(index)) return
    setStepState(key)
  }

  function setDocument(id, title) {
    setDocumentIdState(id)
    setDocumentTitle(title || '')
    const stored = readStoredProgress(id)
    if (stored) setCompletedSteps(stored.completedSteps ?? {})
  }

  function markComplete(key, { toastMessage } = {}) {
    setCompletedSteps((previous) => ({ ...previous, [key]: new Date().toISOString() }))
    if (toastMessage) toast.success(toastMessage)
    const index = STEPS.findIndex((candidate) => candidate.key === key)
    const next = STEPS[index + 1]
    if (next) setStepState(next.key)
  }

  const progressPercent = Math.round((Object.keys(completedSteps).length / STEPS.length) * 100)
  const ActiveStep = STEPS[currentIndex]?.Component ?? STEPS[0].Component

  return (
    <>
      <section className="system-heading">
        <span>Data Workspace</span>
        <h2>Data Workspace Wizard</h2>
        <p>
          Upload a document, run OCR and cleanup, generate chunks, review AI-suggested SFT candidates in the
          AI Review Studio, approve them, and take the first real step of RAG ingestion -- reusing the exact
          same APIs the Documents, Chunk &amp; Record Studio, and Knowledge &amp; RAG pages already use. For
          deep, multi-step document editing, use the existing Documents / Document Wizard / Chunk &amp; Record
          Studio pages directly -- this wizard is a guided, linear on-ramp, not a replacement for them.
        </p>
      </section>

      <div className="wizard-shell">
        <aside className="wizard-progress" aria-label="Wizard progress">
          <div className="wizard-progress-bar" role="progressbar" aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100}>
            <div className="wizard-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <ol>
            {STEPS.map((candidate, index) => {
              const unlocked = stepUnlocked(index)
              const completedAt = completedSteps[candidate.key]
              return (
                <li key={candidate.key}>
                  <button
                    type="button"
                    className={`wizard-step-button ${step === candidate.key ? 'active' : ''} ${completedAt ? 'completed' : ''}`}
                    disabled={!unlocked}
                    aria-current={step === candidate.key ? 'step' : undefined}
                    onClick={() => goToStep(candidate.key)}
                  >
                    <span className="wizard-step-check" aria-hidden="true">{completedAt ? '✓' : index + 1}</span>
                    <span>{candidate.label}</span>
                  </button>
                  {completedAt && <small>{new Date(completedAt).toLocaleTimeString()}</small>}
                </li>
              )
            })}
          </ol>
        </aside>

        <div className="wizard-content">
          <ActiveStep
            documentId={documentId}
            documentTitle={documentTitle}
            onDocumentReady={setDocument}
            onComplete={(options) => markComplete(step, options)}
            onNavigate={onNavigate}
            toast={toast}
          />
          <div className="wizard-nav">
            <Button variant="ghost" disabled={currentIndex <= 0} onClick={() => goToStep(STEPS[currentIndex - 1]?.key)}>
              Back
            </Button>
            <Button
              variant="primary"
              disabled={!completedSteps[step] || currentIndex >= STEPS.length - 1}
              onClick={() => goToStep(STEPS[currentIndex + 1]?.key)}
            >
              Continue
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
