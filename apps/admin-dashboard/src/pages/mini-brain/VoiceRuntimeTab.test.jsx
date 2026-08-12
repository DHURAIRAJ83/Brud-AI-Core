import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VoiceRuntimeTab from './VoiceRuntimeTab.jsx'

function baseProps(overrides = {}) {
  return {
    voSubTab: 'Overview',
    setVoSubTab: vi.fn(),
    voDiag: null,
    voStats: null,
    voConsent: false,
    setVoConsent: vi.fn(),
    voBusy: false,
    voRecording: false,
    startVoRecording: vi.fn(),
    stopVoRecordingAndSend: vi.fn(),
    voSessionData: null,
    voSelectedSessionId: '',
    selectVoSession: vi.fn(),
    voSessionsList: [],
    runVoTestStt: vi.fn(),
    voTestSttText: null,
    voTestTtsForm: { text: '' },
    setVoTestTtsForm: vi.fn(),
    runVoTestTts: vi.fn(),
    voTestTtsResult: null,
    voMetrics: null,
    voEventsList: [],
    voMemoryList: [],
    ...overrides,
  }
}

describe('VoiceRuntimeTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setVoSubTab = vi.fn()
    render(<VoiceRuntimeTab {...baseProps({ setVoSubTab })} />)
    for (const label of ['Overview', 'Public Voice Chat', 'Admin Voice Assistant', 'Sessions', 'STT', 'TTS', 'Permissions', 'Diagnostics', 'Metrics', 'Events', 'Memory', 'Settings', 'History']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'STT' }))
    expect(setVoSubTab).toHaveBeenCalledWith('STT')
  })

  it('Public Voice Chat: real push-to-talk button triggers start/stop handlers', async () => {
    const user = userEvent.setup()
    const startVoRecording = vi.fn()
    const stopVoRecordingAndSend = vi.fn()
    render(<VoiceRuntimeTab {...baseProps({
      voSubTab: 'Public Voice Chat',
      voConsent: true,
      startVoRecording,
      stopVoRecordingAndSend,
    })} />)
    const button = screen.getByRole('button', { name: '🎤 Hold to talk' })
    await user.pointer([{ target: button, keys: '[MouseLeft>]' }])
    expect(startVoRecording).toHaveBeenCalled()
    await user.pointer([{ target: button, keys: '[/MouseLeft]' }])
    expect(stopVoRecordingAndSend).toHaveBeenCalled()
  })

  it('STT: calls the real test action', async () => {
    const user = userEvent.setup()
    const runVoTestStt = vi.fn()
    render(<VoiceRuntimeTab {...baseProps({ voSubTab: 'STT', runVoTestStt })} />)
    await user.click(screen.getByRole('button', { name: 'Record 2s and run STT test' }))
    expect(runVoTestStt).toHaveBeenCalled()
  })

  it('TTS: calls the real test action', async () => {
    const user = userEvent.setup()
    const runVoTestTts = vi.fn()
    render(<VoiceRuntimeTab {...baseProps({ voSubTab: 'TTS', voTestTtsForm: { text: 'hello' }, runVoTestTts })} />)
    await user.click(screen.getByRole('button', { name: 'Run TTS test' }))
    expect(runVoTestTts).toHaveBeenCalled()
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<VoiceRuntimeTab {...baseProps({ voSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
