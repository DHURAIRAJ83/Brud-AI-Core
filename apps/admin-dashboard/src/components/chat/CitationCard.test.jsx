import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CitationCard from './CitationCard.jsx'

describe('CitationCard', () => {
  it('renders a full citation with every real field', () => {
    render(<CitationCard citation={{
      source_name: 'MB48 Grounded Chat Source A',
      source_public_id: 'src-1',
      source_version_public_id: 'ver-12345678',
      rank: 1,
      score: 0.87654,
      text_preview: 'Brud AI is a Tamil-first assistant.',
    }} />)
    expect(screen.getByText('MB48 Grounded Chat Source A')).toBeInTheDocument()
    expect(screen.getByText(/rank 1/)).toBeInTheDocument()
    expect(screen.getByText(/score 0\.88/)).toBeInTheDocument()
    expect(screen.getByText('Brud AI is a Tamil-first assistant.')).toBeInTheDocument()
    expect(screen.getByText(/version ver-1234/)).toBeInTheDocument()
  })

  it('falls back to source_public_id when source_name is absent', () => {
    render(<CitationCard citation={{ source_public_id: 'src-only-id', rank: 2, score: 0.5 }} />)
    expect(screen.getByText('src-only-id')).toBeInTheDocument()
  })

  it('omits text_preview and version blocks when those fields are absent (widget-shaped citation)', () => {
    render(<CitationCard citation={{ source_public_id: 'src-1', source_name: 'Source A', rank: 1, score: 0.6 }} />)
    expect(screen.queryByText(/version/)).not.toBeInTheDocument()
    expect(document.querySelector('.citation-card-preview')).not.toBeInTheDocument()
  })

  it('handles a citation with no rank/score gracefully', () => {
    render(<CitationCard citation={{ source_public_id: 'src-1', source_name: 'Source A' }} />)
    expect(screen.getByText('Source A')).toBeInTheDocument()
  })
})
