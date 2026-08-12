import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  CUSTOM_COLOR_TOKEN_MAP,
  DEFAULT_CUSTOM_COLORS,
  THEME_SCHEMA_VERSION,
  THEME_STORAGE_KEY,
} from './themes.js'

const ThemeContext = createContext(null)

function readStoredTheme() {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    if (parsed.version !== THEME_SCHEMA_VERSION) return null
    return parsed
  } catch {
    // Corrupt JSON, disabled storage, or private-browsing restrictions --
    // fall back to defaults rather than throwing, matching the codebase's
    // existing defensive style (e.g. parseHash's fallback to 'Overview').
    return null
  }
}

function writeStoredTheme(mode, custom) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ version: THEME_SCHEMA_VERSION, mode, custom }))
  } catch {
    // Ignore write failures (quota exceeded, disabled storage, etc.) --
    // the in-memory theme still applies for this session.
  }
}

function applyThemeToDocument(mode, customColors) {
  const root = document.documentElement
  if (mode === 'custom') {
    root.dataset.theme = 'light'
    for (const [key, token] of Object.entries(CUSTOM_COLOR_TOKEN_MAP)) {
      const value = customColors?.[key]
      if (value) root.style.setProperty(token, value)
    }
  } else {
    root.dataset.theme = mode
    for (const token of Object.values(CUSTOM_COLOR_TOKEN_MAP)) {
      root.style.removeProperty(token)
    }
  }
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState('light')
  const [customColors, setCustomColorsState] = useState(null)

  useEffect(() => {
    const stored = readStoredTheme()
    if (stored) {
      setModeState(stored.mode ?? 'light')
      setCustomColorsState(stored.custom ?? null)
    }
  }, [])

  useEffect(() => {
    applyThemeToDocument(mode, mode === 'custom' ? (customColors ?? DEFAULT_CUSTOM_COLORS) : customColors)
  }, [mode, customColors])

  const setMode = useCallback((nextMode) => {
    setModeState(nextMode)
    writeStoredTheme(nextMode, customColors)
  }, [customColors])

  const setCustomColors = useCallback((partialColors) => {
    setCustomColorsState((previous) => {
      const next = { ...DEFAULT_CUSTOM_COLORS, ...previous, ...partialColors }
      writeStoredTheme('custom', next)
      return next
    })
    setModeState('custom')
  }, [])

  const resetCustom = useCallback(() => {
    setCustomColorsState(null)
    writeStoredTheme(mode === 'custom' ? 'light' : mode, null)
    setModeState((previous) => (previous === 'custom' ? 'light' : previous))
  }, [mode])

  const value = useMemo(() => ({
    mode,
    customColors: customColors ?? DEFAULT_CUSTOM_COLORS,
    setMode,
    setCustomColors,
    resetCustom,
  }), [mode, customColors, setMode, setCustomColors, resetCustom])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used within a ThemeProvider')
  return context
}
