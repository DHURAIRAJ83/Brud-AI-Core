import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatMessages from './ChatMessages.jsx'

describe('ChatMessages', () => {
  it('shows the empty state when there are no messages', () => {
    render(<ChatMessages messages={[]} onFeedback={vi.fn()} feedbackSubmitted={{}} />)
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
  })

  it('renders a user message without a route label or feedback controls', () => {
    render(
      <ChatMessages
        messages={[{ id: '1', role: 'user', text: 'Hi' }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    expect(screen.getByText('Hi')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /rate this answer/i })).not.toBeInTheDocument()
  })

  it.each([
    ['core_model', 'Model'],
    ['approved_rag', 'RAG'],
    ['memory', 'Memory'],
    ['trusted_web', 'Web'],
    ['tool', 'Tool'],
    ['clarify', 'Clarification'],
    ['refuse', 'Refused'],
    ['insufficient', 'Unavailable'],
  ])('renders the %s route as the label "%s"', (route, label) => {
    render(
      <ChatMessages
        messages={[{ id: '1', role: 'assistant', text: 'Reply', routeUsed: route, requestId: 'r1' }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('shows feedback controls for an assistant message with a request id', () => {
    render(
      <ChatMessages
        messages={[{ id: '1', role: 'assistant', text: 'Reply', routeUsed: 'core_model', requestId: 'r1' }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    expect(screen.getByRole('button', { name: /^helpful$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /not helpful/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /wrong language/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /unsafe/i })).toBeInTheDocument()
  })

  it('calls onFeedback with the message and feedback type when a feedback button is clicked', async () => {
    const onFeedback = vi.fn()
    const message = { id: '1', role: 'assistant', text: 'Reply', routeUsed: 'core_model', requestId: 'r1' }
    render(<ChatMessages messages={[message]} onFeedback={onFeedback} feedbackSubmitted={{}} />)
    await userEvent.click(screen.getByRole('button', { name: /^helpful$/i }))
    expect(onFeedback).toHaveBeenCalledWith(message, 'thumbs_up')
  })

  it('renders real Web citations as links, never as a citation for a tool answer', () => {
    render(
      <ChatMessages
        messages={[{
          id: '1', role: 'assistant', text: 'Python is a programming language.',
          routeUsed: 'trusted_web', requestId: 'r1',
          citations: [{
            citation_id: 'web:evt:0', title: 'Python (programming language)',
            url: 'https://en.wikipedia.org/wiki/Python_(programming_language)',
          }],
        }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    const link = screen.getByRole('link', { name: /python \(programming language\)/i })
    expect(link).toHaveAttribute('href', 'https://en.wikipedia.org/wiki/Python_(programming_language)')
  })

  it('shows a freshness limitation warning when the Web answer may be stale', () => {
    render(
      <ChatMessages
        messages={[{
          id: '1', role: 'assistant', text: 'Some current-info answer.',
          routeUsed: 'trusted_web', requestId: 'r1', freshnessStatus: 'stale',
          citations: [{ citation_id: 'c1', title: 'Source', url: 'https://example.gov/x' }],
        }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    expect(screen.getByText(/may be out of date/i)).toBeInTheDocument()
  })

  it('shows a source-conflict warning when sources disagreed', () => {
    render(
      <ChatMessages
        messages={[{
          id: '1', role: 'assistant', text: 'Conflicting sources.',
          routeUsed: 'trusted_web', requestId: 'r1',
          limitations: ['source_conflict_disclosed'],
          citations: [
            { citation_id: 'c1', title: 'Source A', url: 'https://a.gov' },
            { citation_id: 'c2', title: 'Source B', url: 'https://b.gov' },
          ],
        }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    expect(screen.getByText(/disagree on this/i)).toBeInTheDocument()
  })

  it('shows the tool name for a tool answer and never shows a citation', () => {
    render(
      <ChatMessages
        messages={[{
          id: '1', role: 'assistant', text: 'Result: 987654 * 12345 = 12193459430',
          routeUsed: 'tool', requestId: 'r1', toolName: 'calculator', toolVersion: 'v1',
          citations: [],
        }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{}}
      />,
    )
    expect(screen.getByText(/tool: calculator/i)).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('shows a thank-you message instead of controls once feedback was submitted', () => {
    render(
      <ChatMessages
        messages={[{ id: '1', role: 'assistant', text: 'Reply', routeUsed: 'core_model', requestId: 'r1' }]}
        onFeedback={vi.fn()}
        feedbackSubmitted={{ 1: 'thumbs_up' }}
      />,
    )
    expect(screen.getByText(/thanks for the feedback/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^helpful$/i })).not.toBeInTheDocument()
  })
})
