import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import Skeleton from './Skeleton.jsx'

describe('Skeleton', () => {
  it('renders a single placeholder line by default', () => {
    render(<Skeleton />)
    const status = screen.getByRole('status', { name: 'Loading' })
    expect(status.querySelectorAll('.skeleton-line')).toHaveLength(1)
  })

  it('renders the requested number of lines', () => {
    render(<Skeleton lines={4} />)
    const status = screen.getByRole('status', { name: 'Loading' })
    expect(status.querySelectorAll('.skeleton-line')).toHaveLength(4)
  })

  it('applies the requested height and width to each line', () => {
    render(<Skeleton lines={1} height="2rem" width="240px" />)
    const line = screen.getByRole('status').querySelector('.skeleton-line')
    expect(line.style.height).toBe('2rem')
    expect(line.style.width).toBe('240px')
  })
})
