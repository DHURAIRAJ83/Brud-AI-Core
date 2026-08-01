import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInput from './ChatInput.jsx'

function setup(overrides = {}) {
  const props = {
    value: '',
    languageOverride: 'auto',
    loading: false,
    onChange: vi.fn(),
    onLanguageOverride: vi.fn(),
    onSubmit: vi.fn((event) => event.preventDefault()),
    ...overrides,
  }
  render(<ChatInput {...props} />)
  return props
}

describe('ChatInput', () => {
  it('offers only Auto, Tamil, and English -- Tanglish is never offered as an output option', () => {
    setup()
    const options = screen.getAllByRole('option').map((option) => option.textContent)
    expect(options).toEqual(['Auto', 'தமிழ்', 'English'])
  })

  it('disables the submit button when the message is empty', () => {
    setup({ value: '' })
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('enables the submit button once text is present', () => {
    setup({ value: 'hello' })
    expect(screen.getByRole('button', { name: /send/i })).toBeEnabled()
  })

  it('disables the textarea, select, and button while loading', () => {
    setup({ value: 'hello', loading: true })
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByRole('button')).toHaveTextContent(/sending/i)
  })

  it('calls onChange as the user types', async () => {
    const props = setup()
    await userEvent.type(screen.getByRole('textbox'), 'x')
    expect(props.onChange).toHaveBeenCalledWith('x')
  })

  it('calls onLanguageOverride when the language selector changes', async () => {
    const props = setup()
    await userEvent.selectOptions(screen.getByRole('combobox'), 'ta')
    expect(props.onLanguageOverride).toHaveBeenCalledWith('ta')
  })

  it('calls onSubmit when the form is submitted', async () => {
    const props = setup({ value: 'hello' })
    await userEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(props.onSubmit).toHaveBeenCalled()
  })
})
