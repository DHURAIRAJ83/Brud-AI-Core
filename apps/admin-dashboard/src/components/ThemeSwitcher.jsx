import { useState } from 'react'
import { useTheme } from '../theme/ThemeProvider.jsx'
import { CUSTOM_COLOR_KEYS } from '../theme/themes.js'
import Button from './Button.jsx'

const MODE_LABELS = { light: 'Light', dark: 'Dark', custom: 'Custom' }
const COLOR_LABELS = {
  primary: 'Primary', secondary: 'Secondary', accent: 'Accent',
  success: 'Success', warning: 'Warning', danger: 'Danger',
}

export default function ThemeSwitcher() {
  const { mode, customColors, setMode, setCustomColors, resetCustom } = useTheme()
  const [pickerOpen, setPickerOpen] = useState(false)

  return (
    <div className="theme-switcher">
      <div className="theme-switcher-modes" role="group" aria-label="Theme">
        {['light', 'dark', 'custom'].map((candidate) => (
          <Button
            key={candidate}
            variant={mode === candidate ? 'primary' : 'ghost'}
            size="sm"
            aria-pressed={mode === candidate}
            onClick={() => {
              if (candidate === 'custom') setPickerOpen(true)
              else setMode(candidate)
            }}
          >
            {MODE_LABELS[candidate]}
          </Button>
        ))}
      </div>
      {pickerOpen && (
        <div role="dialog" aria-modal="true" aria-label="Custom theme colors" className="theme-picker">
          <div className="theme-picker-grid">
            {CUSTOM_COLOR_KEYS.map((key) => (
              <label key={key}>
                {COLOR_LABELS[key]}
                <input
                  type="color"
                  value={customColors[key]}
                  onChange={(event) => setCustomColors({ [key]: event.target.value })}
                />
              </label>
            ))}
          </div>
          <div className="theme-picker-actions">
            <Button variant="ghost" size="sm" onClick={resetCustom}>Reset</Button>
            <Button variant="primary" size="sm" onClick={() => setPickerOpen(false)}>Done</Button>
          </div>
        </div>
      )}
    </div>
  )
}
