import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider, useTheme } from './ThemeProvider.jsx'
import { THEME_STORAGE_KEY } from './themes.js'

function Probe() {
  const { mode, customColors, setMode, setCustomColors, resetCustom } = useTheme()
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="accent">{customColors.accent}</span>
      <button onClick={() => setMode('dark')}>Use dark</button>
      <button onClick={() => setCustomColors({ accent: '#123456' })}>Set custom accent</button>
      <button onClick={() => resetCustom()}>Reset</button>
    </div>
  )
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

describe('ThemeProvider', () => {
  it('defaults to light mode with no stored preference', () => {
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('switching to dark mode updates the document and persists to localStorage', async () => {
    const user = userEvent.setup()
    render(<ThemeProvider><Probe /></ThemeProvider>)
    await user.click(screen.getByRole('button', { name: 'Use dark' }))
    expect(screen.getByTestId('mode')).toHaveTextContent('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(THEME_STORAGE_KEY))
      expect(stored.mode).toBe('dark')
    })
  })

  it('restores a previously stored theme on mount', () => {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ version: 1, mode: 'dark', custom: null }))
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId('mode')).toHaveTextContent('dark')
  })

  it('falls back to defaults when stored JSON is corrupt', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'not valid json{{{')
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
  })

  it('falls back to defaults when the stored schema version does not match', () => {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ version: 99, mode: 'dark', custom: null }))
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
  })

  it('setting a custom color switches to custom mode and merges with defaults', async () => {
    const user = userEvent.setup()
    render(<ThemeProvider><Probe /></ThemeProvider>)
    await user.click(screen.getByRole('button', { name: 'Set custom accent' }))
    expect(screen.getByTestId('mode')).toHaveTextContent('custom')
    expect(screen.getByTestId('accent')).toHaveTextContent('#123456')
    expect(document.documentElement.style.getPropertyValue('--color-accent')).toBe('#123456')
  })

  it('resetCustom clears custom colors and returns to light mode', async () => {
    const user = userEvent.setup()
    render(<ThemeProvider><Probe /></ThemeProvider>)
    await user.click(screen.getByRole('button', { name: 'Set custom accent' }))
    await user.click(screen.getByRole('button', { name: 'Reset' }))
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
    expect(screen.getByTestId('accent')).toHaveTextContent('#65d5a7')
  })

  it('useTheme throws when used outside a ThemeProvider', () => {
    function Bare() {
      useTheme()
      return null
    }
    expect(() => render(<Bare />)).toThrow('useTheme must be used within a ThemeProvider')
  })
})
