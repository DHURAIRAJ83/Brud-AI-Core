import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PromptOptimizationPage from './PromptOptimizationPage.jsx'

vi.mock('../services/api.js', () => ({
  promptLanguageDetect: vi.fn(),
  promptTemplates: vi.fn(),
  promptGenerate: vi.fn(),
  promptCompare: vi.fn(),
}))

const api = await import('../services/api.js')

const TEMPLATES_RESPONSE = { templates: { definition: 'Explain clearly what the subject is.', howto: 'Explain the concrete steps needed.' } }

const DETECT_RESPONSE = {
  language: 'tamil', tamil_char_count: 12, latin_char_count: 0, tamil_ratio: 1.0,
  effective_tamil_ratio: 1.0, tanglish_signal_words: [],
  resolved_output_language: 'tamil', tanglish_normalized_internal: null,
}

const GENERATE_RESPONSE = {
  question: 'What is pending?',
  template_category: 'howto',
  output_language: 'english',
  prompt_used: 'prompt text',
  prompt_length_chars: 120,
  rebuilt: false,
  response: { text: 'Here is what is pending.', backend_type: 'local' },
  validation: { passed: true, issues: [] },
  total_seconds: 1.2,
}

const COMPARE_RESPONSE = {
  question: 'What is pending?',
  template_category: 'howto',
  output_language: 'english',
  baseline: { prompt_length_chars: 200, response: { text: 'baseline answer' }, response_length_chars: 15, seconds: 1.5, validation: { passed: true, issues: [] } },
  optimized: { prompt_length_chars: 120, response: { text: 'optimized answer' }, response_length_chars: 16, seconds: 1.1, validation: { passed: true, issues: [] } },
}

function mockDefaults() {
  api.promptTemplates.mockResolvedValue(TEMPLATES_RESPONSE)
  api.promptLanguageDetect.mockResolvedValue(DETECT_RESPONSE)
  api.promptGenerate.mockResolvedValue(GENERATE_RESPONSE)
  api.promptCompare.mockResolvedValue(COMPARE_RESPONSE)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('PromptOptimizationPage', () => {
  it('loads and renders real templates from the backend', async () => {
    mockDefaults()
    render(<PromptOptimizationPage />)
    expect(await screen.findByText('definition')).toBeInTheDocument()
    expect(await screen.findByText('howto')).toBeInTheDocument()
  })

  it('disables all actions until a question is typed', async () => {
    mockDefaults()
    render(<PromptOptimizationPage />)
    await screen.findByText('definition')
    expect(screen.getByRole('button', { name: 'Detect language' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Generate optimized prompt' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Compare baseline vs optimized' })).toBeDisabled()
  })

  it('runs language detection and shows the real resolved output language', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<PromptOptimizationPage />)
    await user.type(screen.getByPlaceholderText('What is pending review right now?'), 'என்ன நிலுவையில் உள்ளது')
    await user.click(screen.getByRole('button', { name: 'Detect language' }))
    await waitFor(() => expect(api.promptLanguageDetect).toHaveBeenCalledWith('என்ன நிலுவையில் உள்ளது'))
    const detectedCard = await screen.findByText('Detected language')
    expect(detectedCard.closest('article')).toHaveTextContent('tamil')
  })

  it('runs generate and shows the auto-selected template and reply', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<PromptOptimizationPage />)
    await user.type(screen.getByPlaceholderText('What is pending review right now?'), 'What is pending?')
    await user.click(screen.getByRole('button', { name: 'Generate optimized prompt' }))
    await waitFor(() => expect(api.promptGenerate).toHaveBeenCalled())
    expect(await screen.findByText('Generated reply')).toBeInTheDocument()
    expect(await screen.findByText(/Here is what is pending\./)).toBeInTheDocument()
  })

  it('runs compare and shows both baseline and optimized side by side', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<PromptOptimizationPage />)
    await user.type(screen.getByPlaceholderText('What is pending review right now?'), 'What is pending?')
    await user.click(screen.getByRole('button', { name: 'Compare baseline vs optimized' }))
    await waitFor(() => expect(api.promptCompare).toHaveBeenCalled())
    expect(await screen.findByText('Baseline (unmodified prompt)')).toBeInTheDocument()
    expect(await screen.findByText('Optimized (MB-04A)')).toBeInTheDocument()
    expect(await screen.findByText(/baseline answer/)).toBeInTheDocument()
    expect(await screen.findByText(/optimized answer/)).toBeInTheDocument()
  })

  it('shows a generic error notice when generate fails', async () => {
    mockDefaults()
    api.promptGenerate.mockRejectedValue(new Error('Local model unavailable.'))
    const user = userEvent.setup()
    render(<PromptOptimizationPage />)
    await user.type(screen.getByPlaceholderText('What is pending review right now?'), 'What is pending?')
    await user.click(screen.getByRole('button', { name: 'Generate optimized prompt' }))
    expect(await screen.findByText('Local model unavailable.')).toBeInTheDocument()
  })

  it('shows a retry button when templates fail to load and recovers on click', async () => {
    mockDefaults()
    api.promptTemplates.mockRejectedValueOnce(new Error('Network error.'))
    const user = userEvent.setup()
    render(<PromptOptimizationPage />)
    expect(await screen.findByText('Network error.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByText('definition')).toBeInTheDocument())
  })
})
