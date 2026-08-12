export const THEME_STORAGE_KEY = 'brud-admin:theme'
export const THEME_SCHEMA_VERSION = 1

export const THEME_MODES = ['light', 'dark', 'custom']

// Custom-theme color keys an admin can pick, and the defaults shown before
// any override -- matched to the existing brand/status tokens so a fresh
// "custom" theme starts identical to "light" until the admin changes it.
export const CUSTOM_COLOR_KEYS = ['primary', 'secondary', 'accent', 'success', 'warning', 'danger']

export const DEFAULT_CUSTOM_COLORS = {
  primary: '#24334b',
  secondary: '#18243a',
  accent: '#65d5a7',
  success: '#43b989',
  warning: '#e9a650',
  danger: '#efb7b7',
}

// Maps each custom-theme color key to the CSS custom property it overrides.
export const CUSTOM_COLOR_TOKEN_MAP = {
  primary: '--color-sidebar-hover',
  secondary: '--color-sidebar-surface',
  accent: '--color-accent',
  success: '--color-success',
  warning: '--color-warning',
  danger: '--color-danger',
}
