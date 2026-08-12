import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { formatMessageText } from './markdown.jsx'

describe('formatMessageText', () => {
  it('renders plain text unchanged', () => {
    const { container } = render(<div>{formatMessageText('hello world')}</div>)
    expect(container).toHaveTextContent('hello world')
    expect(container.querySelector('strong')).not.toBeInTheDocument()
  })

  it('renders **bold** segments as <strong>', () => {
    const { container } = render(<div>{formatMessageText('this is **important** text')}</div>)
    expect(container.querySelector('strong')).toHaveTextContent('important')
  })

  it('renders `code` segments as <code>', () => {
    const { container } = render(<div>{formatMessageText('run `npm test` now')}</div>)
    expect(container.querySelector('code')).toHaveTextContent('npm test')
  })

  it('renders newlines as <br>', () => {
    const { container } = render(<div>{formatMessageText('line one\nline two')}</div>)
    expect(container.querySelectorAll('br').length).toBeGreaterThan(0)
    expect(container).toHaveTextContent('line one')
    expect(container).toHaveTextContent('line two')
  })

  it('handles combined bold, code, and newlines together', () => {
    const { container } = render(<div>{formatMessageText('**Result:**\nrun `npm test`')}</div>)
    expect(container.querySelector('strong')).toHaveTextContent('Result:')
    expect(container.querySelector('code')).toHaveTextContent('npm test')
    expect(container.querySelectorAll('br').length).toBeGreaterThan(0)
  })

  it('handles empty/null/undefined input without throwing', () => {
    expect(() => render(<div>{formatMessageText('')}</div>)).not.toThrow()
    expect(() => render(<div>{formatMessageText(null)}</div>)).not.toThrow()
    expect(() => render(<div>{formatMessageText(undefined)}</div>)).not.toThrow()
  })
})
