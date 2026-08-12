import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ReleasePipelineTab from './ReleasePipelineTab.jsx'

function baseProps(overrides = {}) {
  return {
    rpDiagnostics: null,
    rpSessions: [],
    rpSelectedId: '',
    selectRpSession: vi.fn(),
    submitRpCreateSession: vi.fn((event) => event?.preventDefault?.()),
    rpCreateForm: {
      core_model_version_public_id: '', pretraining_checkpoint_public_id: '',
      model_release_family_public_id: '', target_quantizations: 'f16,q8_0',
      dataset_version_public_id: '', model_evaluation_run_public_id: '',
    },
    setRpCreateForm: vi.fn(),
    rpBusy: false,
    rpSession: null,
    runRpValidateCheckpoint: vi.fn(),
    runRpConvert: vi.fn(),
    runRpQuantize: vi.fn(),
    runRpVerify: vi.fn(),
    runRpPerformance: vi.fn(),
    submitRpCreateVersion: vi.fn((event) => event?.preventDefault?.()),
    rpVersionForm: { version: '', prerelease_label: '' },
    setRpVersionForm: vi.fn(),
    runRpAdminReview: vi.fn(),
    submitRpActivate: vi.fn((event) => event?.preventDefault?.()),
    rpActivateLevel: '',
    setRpActivateLevel: vi.fn(),
    submitRpEvaluateRollback: vi.fn((event) => event?.preventDefault?.()),
    rpRollbackEvalForm: { target_version: '' },
    setRpRollbackEvalForm: vi.fn(),
    rpRollbackEval: null,
    submitRpExecuteRollback: vi.fn((event) => event?.preventDefault?.()),
    rpRollbackExecuteForm: { target_release_public_id: '', reason: '' },
    setRpRollbackExecuteForm: vi.fn(),
    rpEvents: [],
    ...overrides,
  }
}

describe('ReleasePipelineTab', () => {
  it('shows the real genuinely-supported quantization levels when diagnostics are loaded', () => {
    render(<ReleasePipelineTab {...baseProps({ rpDiagnostics: { quantization_levels_supported: ['f16', 'q8_0'] } })} />)
    expect(screen.getByText(/f16, q8_0/)).toBeInTheDocument()
  })

  it('submits a real new-session form', async () => {
    const user = userEvent.setup()
    const submitRpCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<ReleasePipelineTab {...baseProps({
      rpCreateForm: { core_model_version_public_id: 'cmv-1', pretraining_checkpoint_public_id: '', model_release_family_public_id: '', target_quantizations: 'f16', dataset_version_public_id: '', model_evaluation_run_public_id: '' },
      submitRpCreateSession,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Create session' }))
    expect(submitRpCreateSession).toHaveBeenCalled()
  })

  it('checkpoint_validation stage: calls the real validate action', async () => {
    const user = userEvent.setup()
    const runRpValidateCheckpoint = vi.fn()
    render(<ReleasePipelineTab {...baseProps({
      rpSession: { stage: 'checkpoint_validation', status: 'active', version_string: null, admin_activation_decision: null },
      runRpValidateCheckpoint,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Validate checkpoint' }))
    expect(runRpValidateCheckpoint).toHaveBeenCalled()
  })

  it('awaiting_admin_review stage: approve calls the real handler', async () => {
    const user = userEvent.setup()
    const runRpAdminReview = vi.fn()
    render(<ReleasePipelineTab {...baseProps({
      rpSession: { stage: 'awaiting_admin_review', status: 'active', version_string: 'Brud-0.1', admin_activation_decision: null, release_report: {} },
      runRpAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runRpAdminReview).toHaveBeenCalledWith('approve')
  })

  it('closed stage: shows the real final status and runtime model id', () => {
    render(<ReleasePipelineTab {...baseProps({
      rpSession: { stage: 'closed', status: 'activated', version_string: 'Brud-0.1', admin_activation_decision: 'approve', runtime_model_public_id: 'rm-1' },
    })} />)
    expect(screen.getByText('Runtime model:')).toBeInTheDocument()
    expect(screen.getByText('rm-1')).toBeInTheDocument()
  })

  it('rollback: submits both the real evaluate and execute forms', async () => {
    const user = userEvent.setup()
    const submitRpEvaluateRollback = vi.fn((event) => event?.preventDefault?.())
    const submitRpExecuteRollback = vi.fn((event) => event?.preventDefault?.())
    render(<ReleasePipelineTab {...baseProps({
      rpSession: { stage: 'closed', status: 'activated', version_string: 'Brud-0.1', admin_activation_decision: 'approve' },
      submitRpEvaluateRollback, submitRpExecuteRollback,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Evaluate rollback target' }))
    expect(submitRpEvaluateRollback).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Execute rollback' }))
    expect(submitRpExecuteRollback).toHaveBeenCalled()
  })
})
