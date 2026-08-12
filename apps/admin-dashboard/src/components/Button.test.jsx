import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Button from './Button.jsx'

describe('Button', () => {
  it('renders with the secondary/md defaults', () => {
    render(<Button>Save</Button>)
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button.className).toContain('btn-secondary')
    expect(button.className).toContain('btn-md')
  })

  it('applies the requested variant and size classes', () => {
    render(<Button variant="danger" size="lg">Delete</Button>)
    const button = screen.getByRole('button', { name: 'Delete' })
    expect(button.className).toContain('btn-danger')
    expect(button.className).toContain('btn-lg')
  })

  it('fires onClick when enabled', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={onClick}>Go</Button>)
    await user.click(screen.getByRole('button', { name: 'Go' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('disables the button and blocks clicks while loading', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button loading onClick={onClick}>Submitting</Button>)
    const button = screen.getByRole('button', { name: 'Submitting' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await user.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('renders as an anchor when as="a", without a disabled attribute', () => {
    render(<Button as="a" href="#Overview">Go home</Button>)
    const link = screen.getByRole('link', { name: 'Go home' })
    expect(link.tagName).toBe('A')
    expect(link).not.toHaveAttribute('disabled')
    expect(link.className).toContain('btn')
  })

  it('merges a custom className with the generated classes', () => {
    render(<Button className="extra-class">Hi</Button>)
    expect(screen.getByRole('button', { name: 'Hi' }).className).toContain('extra-class')
  })
})
