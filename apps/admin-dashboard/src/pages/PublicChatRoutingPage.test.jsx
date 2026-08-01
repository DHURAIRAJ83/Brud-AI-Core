import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PublicChatRoutingPage from './PublicChatRoutingPage.jsx'

vi.mock('../services/api.js', () => ({
  publicChatRoutingOverview: vi.fn(),
  publicChatRoutingEvents: vi.fn(),
  publicChatRoutingEvent: vi.fn(),
}))

const api = await import('../services/api.js')

const OVERVIEW = {
  total_requests: 12,
  by_resolved_route: { core_model: 5, approved_rag: 3, memory: 1, clarify: 1, refuse: 1, insufficient: 1 },
  by_safety_status: { safe: 10, refused: 1, output_blocked: 1 },
  clarification_count: 1,
  refusal_count: 1,
  insufficient_count: 1,
  trusted_web_unavailable_count: 2,
  tool_unavailable_count: 1,
  average_latency_ms: 340,
  error_count: 0,
  language_compliance: { total_answered: 11, language_policy_violations: 0 },
}

const EVENT = {
  public_id: 'evt-1',
  request_id: 'req-1',
  input_hash: 'a'.repeat(64),
  resolved_route: 'core_model',
  evidence_status: 'model_only',
  detected_language: 'ta',
  answer_language: 'ta',
  safety_status: 'safe',
  latency_ms: 210,
  created_at: '2026-07-29T00:00:00Z',
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('PublicChatRoutingPage', () => {
  it('renders real overview metrics -- never a fabricated number', async () => {
    api.publicChatRoutingOverview.mockResolvedValue(OVERVIEW)
    render(<PublicChatRoutingPage />)
    await waitFor(() => expect(screen.getByText('Total requests').nextSibling).toHaveTextContent('12'))
    expect(screen.getByRole('heading', { name: /request volume/i })).toBeInTheDocument()
    expect(screen.getByText('Refusals').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Insufficient evidence').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Trusted Web recommended but unavailable').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Tool recommended but unavailable').nextSibling).toHaveTextContent('1')
  })

  it('shows an honest loading state before the overview resolves', () => {
    api.publicChatRoutingOverview.mockReturnValue(new Promise(() => {}))
    render(<PublicChatRoutingPage />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('loads and displays route events with no raw question or answer text', async () => {
    api.publicChatRoutingOverview.mockResolvedValue(OVERVIEW)
    api.publicChatRoutingEvents.mockResolvedValue({ events: [EVENT], count: 1 })
    render(<PublicChatRoutingPage />)
    await waitFor(() => expect(screen.getByText('Total requests').nextSibling).toHaveTextContent('12'))

    await userEvent.click(screen.getByRole('button', { name: 'Route Events' }))
    await waitFor(() => expect(api.publicChatRoutingEvents).toHaveBeenCalled())
    expect(await screen.findByText('core_model')).toBeInTheDocument()
    expect(screen.getAllByText(/no raw question or answer text/i).length).toBeGreaterThan(0)
  })

  it('loads one event detail on demand', async () => {
    api.publicChatRoutingOverview.mockResolvedValue(OVERVIEW)
    api.publicChatRoutingEvents.mockResolvedValue({ events: [EVENT], count: 1 })
    api.publicChatRoutingEvent.mockResolvedValue(EVENT)
    render(<PublicChatRoutingPage />)
    await waitFor(() => expect(screen.getByText('Total requests').nextSibling).toHaveTextContent('12'))
    await userEvent.click(screen.getByRole('button', { name: 'Route Events' }))
    await screen.findByText('core_model')
    await userEvent.click(screen.getByRole('button', { name: 'Details' }))
    await waitFor(() => expect(api.publicChatRoutingEvent).toHaveBeenCalledWith('evt-1'))
  })

  it('filters events by route when switching to a route-specific tab', async () => {
    api.publicChatRoutingOverview.mockResolvedValue(OVERVIEW)
    api.publicChatRoutingEvents.mockResolvedValue({ events: [], count: 0 })
    render(<PublicChatRoutingPage />)
    await waitFor(() => expect(screen.getByText('Total requests').nextSibling).toHaveTextContent('12'))
    await userEvent.click(screen.getByRole('button', { name: 'Clarifications' }))
    await waitFor(() =>
      expect(api.publicChatRoutingEvents).toHaveBeenCalledWith('?resolved_route=clarify'),
    )
  })

  it('renders safety and language-compliance tabs from real overview data', async () => {
    api.publicChatRoutingOverview.mockResolvedValue(OVERVIEW)
    render(<PublicChatRoutingPage />)
    await waitFor(() => expect(screen.getByText('Total requests').nextSibling).toHaveTextContent('12'))

    await userEvent.click(screen.getByRole('button', { name: 'Safety' }))
    expect(screen.getByText('refused').nextSibling).toHaveTextContent('1')

    await userEvent.click(screen.getByRole('button', { name: 'Language Compliance' }))
    expect(screen.getByText('Language policy violations').nextSibling).toHaveTextContent('0')
  })
})
