import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import FutureModelTab from './FutureModelTab.jsx'

describe('FutureModelTab', () => {
  it('renders the real static placeholder content pointing to Local Setup, Runtime Manager, and Assistant Intelligence', () => {
    render(<FutureModelTab />)
    expect(screen.getByText('Local Setup')).toBeInTheDocument()
    expect(screen.getByText('Runtime Manager')).toBeInTheDocument()
    expect(screen.getByText('Assistant Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Provider Settings')).toBeInTheDocument()
    expect(screen.getByText('POST /api/admin/mini-brain/inference')).toBeInTheDocument()
  })
})
