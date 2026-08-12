import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CapabilityTab from './CapabilityTab.jsx'

const RESULT = {
  profile: { display_name: 'qwen2.5-0.5b', verified: true, source: 'benchmark', reasoning_quality: 'fair', coding_quality: 'fair', response_limits: { max_tokens_ceiling: 512 } },
  category: 'howto',
  strategy: { name: 'default' },
  retry: { attempted: false },
  output_length: { word_count: 42, issues: [] },
  generation_time_ms: 123,
  max_tokens_used: 200,
  warnings: [],
  response: { text: 'A real generated answer.' },
}

function baseProps(overrides = {}) {
  return {
    capDiagnostics: null,
    runCapabilityGenerate: vi.fn((event) => event?.preventDefault?.()),
    capQuestion: '',
    setCapQuestion: vi.fn(),
    capBusy: false,
    capResult: null,
    ...overrides,
  }
}

describe('CapabilityTab', () => {
  it('submits a real question through the form', async () => {
    const user = userEvent.setup()
    const runCapabilityGenerate = vi.fn((event) => event?.preventDefault?.())
    render(<CapabilityTab {...baseProps({ capQuestion: 'How does X work?', runCapabilityGenerate })} />)
    await user.click(screen.getByRole('button', { name: 'Generate with capability optimization' }))
    expect(runCapabilityGenerate).toHaveBeenCalled()
  })

  it('shows the real capability result and final response text', () => {
    render(<CapabilityTab {...baseProps({ capResult: RESULT })} />)
    expect(screen.getByText('Current model').closest('article')).toHaveTextContent('qwen2.5-0.5b')
    expect(screen.getByText('A real generated answer.')).toBeInTheDocument()
    expect(screen.getByText('No warnings.')).toBeInTheDocument()
  })

  it('shows real warnings when present', () => {
    render(<CapabilityTab {...baseProps({ capResult: { ...RESULT, warnings: ['Output truncated.'] } })} />)
    expect(screen.getByText('Output truncated.')).toBeInTheDocument()
  })
})
