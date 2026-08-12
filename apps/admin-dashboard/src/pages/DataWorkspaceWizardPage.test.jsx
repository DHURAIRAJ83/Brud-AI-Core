import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '../components/Toast.jsx'
import DataWorkspaceWizardPage from './DataWorkspaceWizardPage.jsx'

// Each step is tested in isolation in pages/wizard/*.test.jsx -- here we
// only need to exercise the wizard SHELL's own logic (locking, auto-advance,
// sessionStorage, URL sync), so every step is replaced with a minimal real
// stub that still calls the real onComplete/onDocumentReady callbacks.
vi.mock('./wizard/UploadStep.jsx', () => ({
  default: ({ onDocumentReady, onComplete }) => (
    <div>
      <span>Upload step</span>
      <button onClick={() => { onDocumentReady('doc-1', 'brud.pdf'); onComplete({ toastMessage: 'Uploaded.' }) }}>
        Finish upload
      </button>
    </div>
  ),
}))
vi.mock('./wizard/OcrStep.jsx', () => ({
  default: ({ onComplete }) => <div><span>OCR step</span><button onClick={() => onComplete({ toastMessage: 'OCR done.' })}>Finish OCR</button></div>,
}))
vi.mock('./wizard/CleanStep.jsx', () => ({
  default: ({ onComplete }) => <div><span>Clean step</span><button onClick={() => onComplete()}>Finish clean</button></div>,
}))
vi.mock('./wizard/ChunkStep.jsx', () => ({
  default: ({ onComplete }) => <div><span>Chunk step</span><button onClick={() => onComplete()}>Finish chunk</button></div>,
}))
vi.mock('./wizard/AiReviewStudioStep.jsx', () => ({
  default: ({ onComplete }) => <div><span>Review step</span><button onClick={() => onComplete()}>Finish review</button></div>,
}))
vi.mock('./wizard/ApproveStep.jsx', () => ({
  default: ({ onComplete }) => <div><span>Approve step</span><button onClick={() => onComplete()}>Finish approve</button></div>,
}))
vi.mock('./wizard/BuildRagStep.jsx', () => ({
  default: ({ onComplete }) => <div><span>Build RAG step</span><button onClick={() => onComplete()}>Finish build rag</button></div>,
}))

function renderWizard() {
  return render(<ToastProvider><DataWorkspaceWizardPage onNavigate={vi.fn()} /></ToastProvider>)
}

beforeEach(() => {
  window.history.replaceState(null, '', '#Data Workspace Wizard')
  sessionStorage.clear()
})

afterEach(() => {
  sessionStorage.clear()
})

describe('DataWorkspaceWizardPage', () => {
  it('renders all 7 steps with only the first unlocked initially', () => {
    renderWizard()
    for (const label of ['Upload', 'OCR', 'Clean', 'Chunk', 'AI Review Studio', 'Approve', 'Build RAG']) {
      expect(screen.getByRole('button', { name: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) })).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: /^OCR/ })).toBeDisabled()
    expect(screen.getByText('Upload step')).toBeInTheDocument()
  })

  it('completing a step shows its green check, unlocks the next, and auto-advances', async () => {
    const user = userEvent.setup()
    renderWizard()
    await user.click(screen.getByRole('button', { name: 'Finish upload' }))
    expect(await screen.findByText('OCR step')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Upload/ }).querySelector('.wizard-step-check')).toHaveTextContent('✓')
    expect(screen.getByRole('button', { name: /^OCR/ })).toBeEnabled()
    expect(screen.getByRole('button', { name: /^Clean/ })).toBeDisabled()
  })

  it('Back and Continue navigate between unlocked steps', async () => {
    const user = userEvent.setup()
    renderWizard()
    await user.click(screen.getByRole('button', { name: 'Finish upload' }))
    await screen.findByText('OCR step')
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText('Upload step')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByText('OCR step')).toBeInTheDocument()
  })

  it('persists progress to sessionStorage and restores it after a simulated refresh', async () => {
    const user = userEvent.setup()
    const { unmount } = renderWizard()
    await user.click(screen.getByRole('button', { name: 'Finish upload' }))
    await screen.findByText('OCR step')
    unmount()

    renderWizard()
    expect(await screen.findByText('OCR step')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^OCR/ })).toBeEnabled()
  })

  it('encodes the current step in the URL hash for deep-linking', async () => {
    const user = userEvent.setup()
    renderWizard()
    await user.click(screen.getByRole('button', { name: 'Finish upload' }))
    await screen.findByText('OCR step')
    expect(window.location.hash).toContain('step=ocr')
    expect(window.location.hash).toContain('document=doc-1')
  })
})
