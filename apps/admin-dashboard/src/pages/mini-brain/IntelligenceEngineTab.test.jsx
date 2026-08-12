import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IntelligenceEngineTab from './IntelligenceEngineTab.jsx'

const RESULT = {
  question_analysis: { intent: 'howto', question_type: 'procedural' },
  response_plan: { suggested_response_type: 'step_by_step' },
  confidence: { score: 0.8, band: 'high', contributions: [{ reason: 'keyword match', points: 5 }] },
  diagnostics: { processing_time_ms: 12, candidate_item_count: 3 },
  knowledge_plan: { primary_knowledge: ['tokenizer'], supporting_knowledge: [], optional_knowledge: [], excluded_knowledge: [] },
  workflow: { current_step: 'train', previous_steps: [], next_steps: [], dependencies: [] },
  context: { matched_item_titles: [], documentation_references: [] },
  features: { dashboard_pages: [], backend_services: [], apis: [] },
  rules: { flags: [], disclaimers: ['Deterministic only.'] },
}

describe('IntelligenceEngineTab', () => {
  it('submits a real question via the analyze form', async () => {
    const user = userEvent.setup()
    const runIntelligenceAnalysis = vi.fn((event) => event?.preventDefault?.())
    const setIeQuestion = vi.fn()
    render(<IntelligenceEngineTab runIntelligenceAnalysis={runIntelligenceAnalysis} ieQuestion="How do I train?" setIeQuestion={setIeQuestion} ieBusy={false} ieResult={null} />)
    await user.click(screen.getByRole('button', { name: 'Analyze' }))
    expect(runIntelligenceAnalysis).toHaveBeenCalled()
  })

  it('disables the button while busy', () => {
    render(<IntelligenceEngineTab runIntelligenceAnalysis={vi.fn()} ieQuestion="x" setIeQuestion={vi.fn()} ieBusy={true} ieResult={null} />)
    expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeDisabled()
  })

  it('shows the real analysis result once available', () => {
    render(<IntelligenceEngineTab runIntelligenceAnalysis={vi.fn()} ieQuestion="" setIeQuestion={vi.fn()} ieBusy={false} ieResult={RESULT} />)
    expect(screen.getByText('Intent').closest('article')).toHaveTextContent('howto')
    expect(screen.getByText('Confidence').closest('article')).toHaveTextContent('0.8 (high)')
    expect(screen.getByText('Deterministic only.')).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /keyword match/ })).toHaveTextContent('5')
  })
})
