import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyToClipboard } from './clipboard.js'

afterEach(() => {
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})

describe('copyToClipboard', () => {
  it('uses navigator.clipboard when available', async () => {
    const writeText = vi.fn().mockResolvedValue()
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const copied = await copyToClipboard('source-1')
    expect(writeText).toHaveBeenCalledWith('source-1')
    expect(copied).toBe(true)
  })

  it('falls back to a hidden textarea when navigator.clipboard is unavailable', async () => {
    vi.stubGlobal('navigator', { clipboard: undefined })
    const execCommand = vi.fn().mockReturnValue(true)
    document.execCommand = execCommand
    const copied = await copyToClipboard('source-1')
    expect(execCommand).toHaveBeenCalledWith('copy')
    expect(copied).toBe(true)
  })

  it('falls back to the textarea when navigator.clipboard.writeText rejects', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const execCommand = vi.fn().mockReturnValue(true)
    document.execCommand = execCommand
    const copied = await copyToClipboard('source-1')
    expect(execCommand).toHaveBeenCalledWith('copy')
    expect(copied).toBe(true)
  })

  it('returns false when both the clipboard API and execCommand fail', async () => {
    vi.stubGlobal('navigator', { clipboard: undefined })
    document.execCommand = vi.fn().mockReturnValue(false)
    const copied = await copyToClipboard('source-1')
    expect(copied).toBe(false)
  })
})
