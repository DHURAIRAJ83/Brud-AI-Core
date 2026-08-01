import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProductionReadinessPage from './ProductionReadinessPage.jsx'

vi.mock('../services/api.js', () => ({
  activateModelRelease: vi.fn(), activateRagReleaseCandidate: vi.fn(),
  approveModelRelease: vi.fn(), approveRagPromotion: vi.fn(),
  assessApiAbuseReadiness: vi.fn(), assessBackupEncryption: vi.fn(),
  assessDeploymentReadiness: vi.fn(),
  buildRagReleaseCandidate: vi.fn(), checkBackupArtifactSecurity: vi.fn(),
  checkBackupReadiness: vi.fn(), checkReleaseCandidateArtifacts: vi.fn(),
  checkRestoreReadiness: vi.fn(), compileReadinessReport: vi.fn(),
  createModelReleaseRequest: vi.fn(), createRagPromotionRequest: vi.fn(),
  createRegressionRun: vi.fn(), createProductionRollbackPlan: vi.fn(),
  encryptLatestBackup: vi.fn(),
  executeModelCanary: vi.fn(), executeRegressionBatch: vi.fn(),
  finalizeRegressionRun: vi.fn(), latestReadinessReport: vi.fn(),
  modelReleaseEligibility: vi.fn(), modelReleaseRequest: vi.fn(),
  modelReleaseRequests: vi.fn(), productionReadinessOverview: vi.fn(),
  productionRagEligibility: vi.fn(), productionSystemHealth: vi.fn(),
  ragPromotionRequest: vi.fn(), ragPromotionRequests: vi.fn(),
  ragReleaseCandidate: vi.fn(), ragReleaseCandidates: vi.fn(),
  scanBackupSidecarFiles: vi.fn(),
  rejectModelReleaseRequest: vi.fn(), requestModelReleaseApproval: vi.fn(),
  requestRagPromotionApproval: vi.fn(), rollbackModelRelease: vi.fn(),
  rollbackRagReleaseCandidate: vi.fn(), startModelCanary: vi.fn(),
  stopModelCanary: vi.fn(), submitAcceptanceReview: vi.fn(),
  submitModelReleaseRequest: vi.fn(), submitRagPromotionRequest: vi.fn(),
  validateModelReleaseRequest: vi.fn(), validateRagReleaseCandidate: vi.fn(),
  validateProductionRollbackPlan: vi.fn(), verifyEncryptedRestore: vi.fn(),
  verifySecretRedaction: vi.fn(),
}))

const api = await import('../services/api.js')

function mockBaseline() {
  api.productionReadinessOverview.mockResolvedValue({
    rag_promotions_awaiting_approval: 0, activation_failures: 2, backups_not_encrypted: 1,
  })
  api.ragPromotionRequests.mockResolvedValue({ items: [] })
  api.modelReleaseRequests.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('ProductionReadinessPage: sub-tab hash deep-linking', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '#Production Readiness')
  })

  it('reads the initial tab from the URL hash query on mount', async () => {
    mockBaseline()
    window.history.replaceState(null, '', '#Production Readiness?tab=Model+Release')
    render(<ProductionReadinessPage />)
    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Model Release' }),
    ).toHaveClass('active'))
  })

  it('falls back to Overview when the hash has no recognized tab', async () => {
    mockBaseline()
    window.history.replaceState(null, '', '#Production Readiness?tab=Nonexistent')
    render(<ProductionReadinessPage />)
    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Overview' }),
    ).toHaveClass('active'))
  })

  it('writes the selected tab back into the URL hash so a refresh preserves it', async () => {
    mockBaseline()
    window.history.replaceState(null, '', '#Production Readiness')
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'RAG Candidates' }))
    await waitFor(() => expect(window.location.hash).toBe('#Production%20Readiness?tab=RAG+Candidates'))
  })
})

describe('ProductionReadinessPage: navigation', () => {
  it('renders all ten required tabs', async () => {
    mockBaseline()
    render(<ProductionReadinessPage />)
    for (const tab of [
      'Overview', 'RAG Promotion', 'RAG Candidates', 'Model Release', 'Canary & Activation',
      'Artifact Security', 'API Abuse & Secrets', 'Backup & Deployment', 'Regression',
      'Readiness Report & Acceptance',
    ]) {
      await waitFor(() => expect(screen.getByRole('button', { name: tab })).toBeInTheDocument())
    }
  })

  it('overview shows real counts, including failure warnings', async () => {
    mockBaseline()
    render(<ProductionReadinessPage />)
    await waitFor(() => expect(screen.getByText('Activation failures').nextSibling).toHaveTextContent('2'))
    await waitFor(() => expect(screen.getByText('Backups not encrypted').nextSibling).toHaveTextContent('1'))
  })
})

describe('ProductionReadinessPage: RAG promotion', () => {
  it('creating a promotion request calls createRagPromotionRequest with form values', async () => {
    mockBaseline()
    api.createRagPromotionRequest.mockResolvedValue({ public_id: 'promo-1', status: 'draft' })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'RAG Promotion' }))
    await user.type(screen.getByPlaceholderText('RAG sandbox experiment public ID'), 'exp-1')
    await user.type(screen.getByPlaceholderText('Knowledge space public ID'), 'space-1')
    await user.click(screen.getByRole('button', { name: 'Create request' }))
    await waitFor(() => expect(api.createRagPromotionRequest).toHaveBeenCalledWith({
      rag_sandbox_experiment_public_id: 'exp-1', knowledge_space_public_id: 'space-1',
    }))
  })

  it('checking RAG eligibility calls productionRagEligibility with the entered id', async () => {
    mockBaseline()
    api.productionRagEligibility.mockResolvedValue({ eligible: false, blocking_reasons: ['not accepted'] })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'RAG Promotion' }))
    await user.type(screen.getByPlaceholderText('Accepted RAG sandbox experiment public ID'), 'exp-2')
    await user.click(screen.getByRole('button', { name: 'Check eligibility' }))
    await waitFor(() => expect(api.productionRagEligibility).toHaveBeenCalledWith('exp-2'))
    await waitFor(() => screen.getByText('not accepted'))
  })
})

describe('ProductionReadinessPage: RAG candidates', () => {
  // Regression test for a real bug found by Phase 15A browser automation:
  // validateRagReleaseCandidate() resolves to {candidate, results}, not a
  // flat candidate -- the page must unwrap `.candidate` before displaying
  // it, or the status/production-visible fields silently render as blank.
  it('validating a candidate displays the unwrapped candidate status, not the wrapper', async () => {
    mockBaseline()
    api.ragReleaseCandidate.mockResolvedValue({
      public_id: 'cand-1', status: 'built', production_visible: false,
    })
    api.validateRagReleaseCandidate.mockResolvedValue({
      candidate: { public_id: 'cand-1', status: 'validated', production_visible: false },
      results: [{ check_type: 'retrieval_profile_ready', result_status: 'passed' }],
    })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'RAG Candidates' }))
    await user.type(screen.getByPlaceholderText('RAG release candidate public ID'), 'cand-1')
    await user.click(screen.getByRole('button', { name: 'Validate' }))
    await waitFor(() => expect(api.validateRagReleaseCandidate).toHaveBeenCalledWith('cand-1'))
    await waitFor(() => screen.getByText('Status: validated'))
  })
})

describe('ProductionReadinessPage: model release', () => {
  it('checking model eligibility calls modelReleaseEligibility with the entered checkpoint id', async () => {
    mockBaseline()
    api.modelReleaseEligibility.mockResolvedValue({ eligible: true, blocking_reasons: [] })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Model Release' }))
    await user.type(screen.getByPlaceholderText('Accepted Phase 14 checkpoint public ID'), 'ckpt-1')
    await user.click(screen.getByRole('button', { name: 'Check eligibility' }))
    await waitFor(() => expect(api.modelReleaseEligibility).toHaveBeenCalledWith('ckpt-1'))
  })
})

describe('ProductionReadinessPage: rollback plans', () => {
  // Regression test for a real bug found by Phase 15A browser automation:
  // the rollback-plan form had no way to enter rollback_steps, so every
  // plan created through the UI defaulted to an empty list and could
  // never pass the backend's "at least one rollback step" validation.
  it('creating a rollback plan sends the entered steps as a trimmed, non-empty array', async () => {
    mockBaseline()
    api.createProductionRollbackPlan.mockResolvedValue({ public_id: 'plan-1', status: 'draft' })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Canary & Activation' }))
    await user.type(
      screen.getByPlaceholderText('Rollback steps (one per line)'),
      'restore previous assignment{enter}  notify on-call  ',
    )
    await user.click(screen.getByRole('button', { name: 'Create plan' }))
    await waitFor(() => expect(api.createProductionRollbackPlan).toHaveBeenCalledWith({
      target_type: 'model', current_active_version: null,
      rollback_steps: ['restore previous assignment', 'notify on-call'],
    }))
  })
})

describe('ProductionReadinessPage: safety checks', () => {
  it('running the API-abuse readiness check calls assessApiAbuseReadiness and shows the result', async () => {
    mockBaseline()
    api.assessApiAbuseReadiness.mockResolvedValue({ result_status: 'passed', findings: [] })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'API Abuse & Secrets' }))
    await user.click(screen.getByRole('button', { name: 'Run API-abuse readiness check' }))
    await waitFor(() => expect(api.assessApiAbuseReadiness).toHaveBeenCalled())
    await waitFor(() => screen.getByText('API abuse readiness: passed'))
  })

  it('scanning backup sidecar files calls scanBackupSidecarFiles and shows the result', async () => {
    mockBaseline()
    api.scanBackupSidecarFiles.mockResolvedValue({ result_status: 'passed', findings: [] })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'API Abuse & Secrets' }))
    await user.click(screen.getByRole('button', { name: 'Scan backup sidecar files for secrets' }))
    await waitFor(() => expect(api.scanBackupSidecarFiles).toHaveBeenCalled())
    await waitFor(() => screen.getByText('Backup sidecar secret scan: passed'))
  })
})

describe('ProductionReadinessPage: backup encryption', () => {
  it('running the backup-encryption assessment calls assessBackupEncryption and shows the honest result', async () => {
    mockBaseline()
    api.assessBackupEncryption.mockResolvedValue({
      result_status: 'not_encrypted', findings: ['latest_backup_not_encrypted'],
    })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Backup & Deployment' }))
    await user.click(screen.getByRole('button', { name: 'Assess backup encryption' }))
    await waitFor(() => expect(api.assessBackupEncryption).toHaveBeenCalled())
    await waitFor(() => screen.getByText('Backup encryption: not_encrypted'))
    await waitFor(() => screen.getByText('latest_backup_not_encrypted'))
  })

  it('encrypting the latest backup calls encryptLatestBackup and shows the encrypted filename', async () => {
    mockBaseline()
    api.encryptLatestBackup.mockResolvedValue({
      result_status: 'encrypted', encrypted_filename: 'brud_ai_before_v38_x.db.enc',
    })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Backup & Deployment' }))
    await user.click(screen.getByRole('button', { name: 'Encrypt latest backup' }))
    await waitFor(() => expect(api.encryptLatestBackup).toHaveBeenCalled())
    await waitFor(() => screen.getByText('Encrypted: brud_ai_before_v38_x.db.enc'))
  })

  it('verifying the encrypted restore calls verifyEncryptedRestore and shows the honest result', async () => {
    mockBaseline()
    api.verifyEncryptedRestore.mockResolvedValue({
      result_status: 'blocked', findings: ['decrypt_failed: wrong key or corrupted/tampered ciphertext'],
    })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Backup & Deployment' }))
    await user.click(screen.getByRole('button', { name: 'Verify encrypted restore (isolated drill)' }))
    await waitFor(() => expect(api.verifyEncryptedRestore).toHaveBeenCalled())
    await waitFor(() => screen.getByText('Encrypted restore drill: blocked'))
  })
})

describe('ProductionReadinessPage: readiness report', () => {
  it('compiling a report calls compileReadinessReport and shows the recommendation', async () => {
    mockBaseline()
    api.compileReadinessReport.mockResolvedValue({
      public_id: 'report-1', report_version: 1, recommendation: 'not_ready',
      report_checksum_sha256: 'abc',
    })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Readiness Report & Acceptance' }))
    await user.click(screen.getByRole('button', { name: 'Compile new readiness report' }))
    await waitFor(() => expect(api.compileReadinessReport).toHaveBeenCalled())
    await waitFor(() => screen.getByText('v1: not_ready'))
  })

  it('submitting the acceptance review calls submitAcceptanceReview with the report id', async () => {
    mockBaseline()
    api.compileReadinessReport.mockResolvedValue({
      public_id: 'report-1', report_version: 1, recommendation: 'not_ready',
      report_checksum_sha256: 'abc',
    })
    api.submitAcceptanceReview.mockResolvedValue({ public_id: 'review-1', decision: 'needs_remediation' })
    const user = userEvent.setup()
    render(<ProductionReadinessPage />)
    await user.click(await screen.findByRole('button', { name: 'Readiness Report & Acceptance' }))
    await user.click(screen.getByRole('button', { name: 'Compile new readiness report' }))
    await waitFor(() => screen.getByText('v1: not_ready'))
    await user.selectOptions(screen.getByRole('combobox'), 'needs_remediation')
    await user.type(screen.getByPlaceholderText('Reason'), 'nothing assessed yet')
    await user.click(screen.getByRole('button', { name: 'Record decision' }))
    await waitFor(() => expect(api.submitAcceptanceReview).toHaveBeenCalledWith('report-1', {
      decision: 'needs_remediation', reason: 'nothing assessed yet',
    }))
  })
})
