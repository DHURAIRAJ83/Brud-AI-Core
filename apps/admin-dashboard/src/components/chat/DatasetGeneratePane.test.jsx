import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DatasetGeneratePane from './DatasetGeneratePane.jsx'
import * as api from '../../services/api.js'

vi.mock('../../services/api.js', () => ({
  psProviders: vi.fn(),
  mdCreateSession: vi.fn(),
  mdSession: vi.fn(),
  mdRunCollectSources: vi.fn(),
  mdRunCollectText: vi.fn(),
  mdRunCollectImages: vi.fn(),
  mdRunMergeMetadata: vi.fn(),
  mdRunConversationBuilder: vi.fn(),
  mdRunInstructionBuilder: vi.fn(),
  mdRunDatasetDraft: vi.fn(),
  mdRunQualityAnalysis: vi.fn(),
  mdRunDuplicateDetection: vi.fn(),
  mdGenerateReport: vi.fn(),
  mdRecords: vi.fn(),
  mdAdminReview: vi.fn(),
}))

describe('DatasetGeneratePane', () => {
  const toast = { success: vi.fn(), error: vi.fn() }
  const onNavigate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    api.psProviders.mockResolvedValue({
      items: [
        {
          public_id: 'prov-openrouter',
          provider_key: 'openrouter',
          enabled: true,
        },
      ],
    })
    api.mdCreateSession.mockResolvedValue({
      public_id: 'md-sess-12345678',
      stage: 'collect_sources',
      status: 'draft',
    })
    api.mdRunCollectSources.mockResolvedValue({ stage: 'collect_text' })
    api.mdRunCollectText.mockResolvedValue({ stage: 'collect_images' })
    api.mdRunCollectImages.mockResolvedValue({ stage: 'merge_metadata' })
    api.mdRunMergeMetadata.mockResolvedValue({ stage: 'conversation_builder' })
    api.mdRunConversationBuilder.mockResolvedValue({ stage: 'instruction_builder' })
    api.mdRunInstructionBuilder.mockResolvedValue({ stage: 'dataset_draft' })
    api.mdRunDatasetDraft.mockResolvedValue({ stage: 'quality_analysis' })
    api.mdRunQualityAnalysis.mockResolvedValue({ stage: 'duplicate_detection', quality_report: { overall_dataset_quality: 94 } })
    api.mdRunDuplicateDetection.mockResolvedValue({ stage: 'report' })
    api.mdGenerateReport.mockResolvedValue({
      public_id: 'md-sess-12345678',
      stage: 'awaiting_admin_review',
      status: 'draft',
      quality_report: { overall_dataset_quality: 94 },
    })
    api.mdRecords.mockResolvedValue({
      items: [
        {
          public_id: 'rec-1',
          record_type: 'instruction',
          record_checksum: 'a1b2c3d4e5f6',
          content: { instruction: 'Explain Tamil grammar', response: 'Tamil grammar has 5 parts.' },
        },
      ],
    })
    api.mdAdminReview.mockResolvedValue({
      public_id: 'md-sess-12345678',
      status: 'admin_approved',
    })
  })

  it('renders form controls with topic, language, and provider choices', async () => {
    render(<DatasetGeneratePane toast={toast} onNavigate={onNavigate} />)
    await waitFor(() => {
      expect(screen.getByText('Provider Dataset Generator')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Tamil language & administrative reasoning')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Generate Dataset Cycle' })).toBeInTheDocument()
    })
  })

  it('executes full MB-16 pipeline and renders records preview with governance review', async () => {
    render(<DatasetGeneratePane toast={toast} onNavigate={onNavigate} />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Generate Dataset Cycle' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Generate Dataset Cycle' }))

    await waitFor(() => {
      expect(api.mdCreateSession).toHaveBeenCalled()
      expect(api.mdRunDatasetDraft).toHaveBeenCalled()
      expect(api.mdRunQualityAnalysis).toHaveBeenCalled()
      expect(api.mdGenerateReport).toHaveBeenCalled()
      expect(screen.getByText('Generated Record Preview (1 records)')).toBeInTheDocument()
      expect(screen.getByText('Admin Governance & Certification Gate')).toBeInTheDocument()
    })

    // Click Certify Dataset
    const certifyBtn = screen.getByRole('button', { name: 'Certify Dataset' })
    fireEvent.click(certifyBtn)

    await waitFor(() => {
      expect(api.mdAdminReview).toHaveBeenCalledWith('md-sess-12345678', 'approve')
      expect(toast.success).toHaveBeenCalledWith('Dataset Certified.')
    })
  })
})
