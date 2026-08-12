import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DatasetIntelligenceTab from './DatasetIntelligenceTab.jsx'

const DI_REPORT = {
  overall_status: 'Ready',
  scores: { overall: { score: 90 } },
  records_analyzed: 100,
  dataset_summary: { by_record_type: { qa: 100 } },
  processing_time_ms: 12,
  warnings: [],
  quality_report: { clean_ratio: 0.9, flagged_records: 1, empty_content_records: 0, broken_reference_records: 0, issue_counts: {} },
  duplicates: {},
  language_report: { distribution_percentages: { en: 100 }, token_estimation: {} },
  domain: { category: 'general', reason: 'r', topic_scores: {} },
  training_report: { status: 'Ready', reasons: [] },
  rag_report: { status: 'Ready', chunk_suitability_ratio: 1, citation_readiness_ratio: 1, reasons: [], missing_titles: '' },
  sft_report: { status: 'Ready', instruction_quality_ratio: 1, answer_completeness_ratio: 1, reasons: [] },
  recommendations: [],
}

function baseProps(overrides = {}) {
  return {
    runDatasetIntelligenceReport: vi.fn((event) => event?.preventDefault?.()),
    diSourceId: '',
    setDiSourceId: vi.fn(),
    diBusy: false,
    diSubTab: 'Overview',
    setDiSubTab: vi.fn(),
    diReport: null,
    diDiagnostics: null,
    toggleAdvanced: vi.fn(),
    showAdvanced: false,
    advBusy: false,
    runAdvancedReport: vi.fn((event) => event?.preventDefault?.()),
    advSubTab: 'Overview',
    setAdvSubTab: vi.fn(),
    advReport: null,
    advDiagnostics: null,
    ...overrides,
  }
}

describe('DatasetIntelligenceTab', () => {
  it('submits a real source id through the report form', async () => {
    const user = userEvent.setup()
    const runDatasetIntelligenceReport = vi.fn((event) => event?.preventDefault?.())
    render(<DatasetIntelligenceTab {...baseProps({ diSourceId: 'src-1', runDatasetIntelligenceReport })} />)
    await user.click(screen.getByRole('button', { name: 'Run full report' }))
    expect(runDatasetIntelligenceReport).toHaveBeenCalled()
  })

  it('shows the real Overview report once loaded, and an honest empty-state before that', () => {
    const { rerender } = render(<DatasetIntelligenceTab {...baseProps()} />)
    expect(screen.getByText(/Enter a dataset source public ID above/)).toBeInTheDocument()
    rerender(<DatasetIntelligenceTab {...baseProps({ diReport: DI_REPORT })} />)
    expect(screen.getByText('Overall status').closest('article')).toHaveTextContent('Ready')
    expect(screen.getByText('Records analyzed').closest('article')).toHaveTextContent('100')
  })

  it('switches to the real Quality sub-tab on click', async () => {
    const user = userEvent.setup()
    const setDiSubTab = vi.fn()
    render(<DatasetIntelligenceTab {...baseProps({ diReport: DI_REPORT, setDiSubTab })} />)
    await user.click(screen.getByRole('button', { name: 'Quality' }))
    expect(setDiSubTab).toHaveBeenCalledWith('Quality')
  })

  it('toggles the real Advanced Dataset Intelligence section', async () => {
    const user = userEvent.setup()
    const toggleAdvanced = vi.fn()
    render(<DatasetIntelligenceTab {...baseProps({ toggleAdvanced })} />)
    await user.click(screen.getByRole('button', { name: 'Show advanced section' }))
    expect(toggleAdvanced).toHaveBeenCalled()
  })

  it('shows real advanced report content once expanded and loaded', () => {
    render(<DatasetIntelligenceTab {...baseProps({
      showAdvanced: true,
      advReport: {
        scores: { overall: { score: 70 } },
        conflicts: { conflict_count: 2, conflict_groups: [{ question_preview: 'q', distinct_answers: ['a', 'b'] }] },
        risk: { risk_item_count: 0, risk_score: 0, category_counts: {} },
        records_analyzed: 50,
        processing_time_ms: 5,
      },
    })} />)
    expect(screen.getByText('Conflicts').closest('article')).toHaveTextContent('2')
  })

  it('Conflict sub-tab: shows the real conflict groups', () => {
    render(<DatasetIntelligenceTab {...baseProps({
      showAdvanced: true,
      advSubTab: 'Conflict',
      advReport: {
        scores: { overall: { score: 70 } },
        conflicts: { conflict_count: 1, conflict_groups: [{ question_preview: 'q', distinct_answers: ['a', 'b'] }] },
        risk: { risk_item_count: 0, risk_score: 0, category_counts: {} },
        records_analyzed: 50,
        processing_time_ms: 5,
      },
    })} />)
    expect(screen.getByText('q')).toBeInTheDocument()
    expect(screen.getByText(/a \| b/)).toBeInTheDocument()
  })
})
