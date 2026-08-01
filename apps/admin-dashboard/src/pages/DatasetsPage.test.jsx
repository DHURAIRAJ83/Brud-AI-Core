import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import DatasetsPage from './DatasetsPage.jsx'

vi.mock('../services/api.js', () => ({
  assessQuality: vi.fn(), assessRecordQuality: vi.fn(), createDatasetBuild: vi.fn(),
  createDatasetExport: vi.fn(), createDatasetRecord: vi.fn(), createDatasetSource: vi.fn(),
  datasetBuilds: vi.fn(), datasetDuplicates: vi.fn(), datasetRecords: vi.fn(),
  datasetSources: vi.fn(), datasetStatistics: vi.fn(), datasetVersions: vi.fn(),
  lineageForEntity: vi.fn(), qualityIssues: vi.fn(), qualitySummary: vi.fn(),
  recordAction: vi.fn(), recordReviews: vi.fn(), runDatasetBuild: vi.fn(),
  updateDatasetRecord: vi.fn(), updateDatasetSource: vi.fn(), validateDatasetBuild: vi.fn(),
  verifyDatasetVersion: vi.fn(),
}))

const api = await import('../services/api.js')

function mockBaseline() {
  api.datasetSources.mockResolvedValue({ items: [] })
  api.datasetStatistics.mockResolvedValue({ by_status: {}, by_language: {}, by_record_type: {} })
  api.datasetVersions.mockResolvedValue({
    items: [
      { public_id: 'ver-1', name: 'brud', version: 'v1', status: 'completed', record_count: 3, checksum_sha256: 'abc' },
      { public_id: 'ver-2', name: 'brud', version: 'v2', status: 'completed', record_count: 5, checksum_sha256: 'def' },
    ],
  })
  api.datasetBuilds.mockResolvedValue({ items: [] })
}

afterEach(() => { vi.resetAllMocks() })

describe('DatasetsPage: dataset-version deep link', () => {
  it('defaults to the Overview tab with no initialVersionPublicId', async () => {
    mockBaseline()
    render(<DatasetsPage />)
    await waitFor(() => expect(screen.getByText('Dataset overview')).toBeInTheDocument())
  })

  it('opens the Versions tab and highlights the matching version when initialVersionPublicId is given', async () => {
    mockBaseline()
    render(<DatasetsPage initialVersionPublicId="ver-2" />)
    await waitFor(() => expect(screen.getByText('Dataset versions')).toBeInTheDocument())
    const article = document.getElementById('dataset-version-ver-2')
    expect(article).toBeInTheDocument()
    expect(article.className).toContain('active')
    expect(document.getElementById('dataset-version-ver-1').className).not.toContain('active')
  })

  it('shows a non-fatal notice when the requested version is not in the list', async () => {
    mockBaseline()
    render(<DatasetsPage initialVersionPublicId="ver-unknown" />)
    await waitFor(() => expect(screen.getByText(/dataset version was not found/)).toBeInTheDocument())
  })
})
