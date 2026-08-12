import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResponseQualityTab from './ResponseQualityTab.jsx'

const RESULT = {
  quality: {
    quality_score: { overall_quality: 80, echo_score: 100, language_score: 90, tamil_score: null, formatting_score: 95, consistency_score: 90 },
    echo: { echo_detected: false, echo_type: 'none', severity: 'none', overlap_ratio: 0, overlap_length_chars: 0, matched_labels: [] },
    language: { language: 'en', resolved_output_language: 'en', expected_output_language: 'en', matches_expectation: true },
    formatting: { passed: true, issues: [] },
    consistency: { passed: true, issues: [] },
    actions_performed: [],
    processing_time_ms: 5,
  },
  final_response_text: 'A real answer.',
}

function baseProps(overrides = {}) {
  return {
    qDiagnostics: null,
    runQualityGenerate: vi.fn((event) => event?.preventDefault?.()),
    qQuestion: '',
    setQQuestion: vi.fn(),
    qBusy: false,
    qResult: null,
    qHistory: [],
    ...overrides,
  }
}

describe('ResponseQualityTab', () => {
  it('submits a real question through the form', async () => {
    const user = userEvent.setup()
    const runQualityGenerate = vi.fn((event) => event?.preventDefault?.())
    render(<ResponseQualityTab {...baseProps({ qQuestion: 'How does X work?', runQualityGenerate })} />)
    await user.click(screen.getByRole('button', { name: 'Generate and check quality' }))
    expect(runQualityGenerate).toHaveBeenCalled()
  })

  it('shows the real quality result and final response text', () => {
    render(<ResponseQualityTab {...baseProps({ qResult: RESULT })} />)
    expect(screen.getByText('Overall quality').closest('article')).toHaveTextContent('80')
    expect(screen.getByText('A real answer.')).toBeInTheDocument()
  })

  it('shows the honest fallback when nothing survived echo cleanup', () => {
    render(<ResponseQualityTab {...baseProps({ qResult: { ...RESULT, final_response_text: '' } })} />)
    expect(screen.getByText(/No substantive answer survived echo cleanup/)).toBeInTheDocument()
  })

  it('shows real session-local diagnostic history entries', () => {
    render(<ResponseQualityTab {...baseProps({ qHistory: [{ overall: 80, question: 'Q1', at: '10:00' }] })} />)
    expect(screen.getByText('Q1', { exact: false })).toBeInTheDocument()
  })
})
