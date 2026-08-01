import { useEffect, useState } from 'react'
import {
  addGovernanceReviewItemNote, assessGovernanceQuality, assignGovernanceReviewItem,
  evaluateGovernanceApproval, governanceApprovalStatus, governanceConflictGroups,
  governanceDuplicateGroups, governanceExportReadiness, governanceQueue, governanceReviewItem,
  governanceReviewItemHistory, openGovernanceReviewItem, overrideGovernanceApproval,
  resolveGovernanceConflictGroup, resolveGovernanceDuplicateGroup, setGovernanceReviewItemStatus,
  syncChunkDuplicate, syncManualDataDuplicate, syncStructuredRecordConflict,
} from '../services/api.js'

const tabs = [
  'Overview', 'Queue', 'Review Detail', 'Quality', 'Duplicates', 'Conflicts',
  'Approvals', 'Export Readiness', 'History',
]

const ENTITY_TYPES = [
  'document_page', 'manual_data_record', 'semantic_chunk',
  'structured_record_candidate', 'document_candidate', 'dataset_record',
]

const REVIEW_STATUSES = [
  'open', 'in_review', 'waiting_for_correction', 'waiting_for_source',
  'waiting_for_verification', 'resolved', 'rejected', 'archived',
]

const PRIORITIES = ['low', 'normal', 'high', 'urgent']

const TARGET_USES = [
  'rag', 'training', 'evaluation', 'commercial', 'public_export',
  'redistribution', 'dataset_export', 'rag_handoff',
]

const RESOLUTION_ACTIONS = [
  'keep_all', 'choose_canonical', 'mark_alternate', 'merge_manually', 'reject_selected',
  'archive_selected', 'not_a_duplicate', 'keep_both_with_context', 'mark_alternate_sense',
  'mark_alternate_answer', 'choose_preferred_translation', 'request_domain_review',
  'request_source_verification', 'resolve_with_new_revision',
]

export default function GovernancePage() {
  const [tab, setTab] = useState('Overview')
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState('')

  const [queueItems, setQueueItems] = useState([]), [queueCounts, setQueueCounts] = useState({})
  const [queueFilters, setQueueFilters] = useState({ status: '', priority: '', entity_type: '' })

  const [selectedReviewId, setSelectedReviewId] = useState('')
  const [reviewDetail, setReviewDetail] = useState(null)
  const [reviewHistory, setReviewHistory] = useState(null)

  const [entityType, setEntityType] = useState('manual_data_record')
  const [entityPublicId, setEntityPublicId] = useState('')

  const [duplicateGroups, setDuplicateGroups] = useState([])
  const [conflictGroups, setConflictGroups] = useState([])

  useEffect(() => { loadQueue() }, [])

  async function loadQueue(filters = queueFilters) {
    try {
      const query = Object.entries(filters).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
      const result = await governanceQueue(query ? `?${query}` : '')
      setQueueItems(result.items)
      setQueueCounts(result.counts_by_status || {})
    } catch (reason) { setError(reason.message) }
  }

  async function openReview(id) {
    try {
      setSelectedReviewId(id)
      setReviewDetail(await governanceReviewItem(id))
      setTab('Review Detail')
    } catch (reason) { setError(reason.message) }
  }

  async function reviewAction(label, callback) {
    setBusy(label); setError('')
    try {
      const result = await callback()
      setNotice(`${label} completed.`)
      if (selectedReviewId) setReviewDetail(await governanceReviewItem(selectedReviewId))
      await loadQueue()
      return result
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function loadDuplicates(status) {
    try { setDuplicateGroups((await governanceDuplicateGroups(status ? `?status=${status}` : '')).items) } catch (reason) { setError(reason.message) }
  }

  async function loadConflicts(status) {
    try { setConflictGroups((await governanceConflictGroups(status ? `?status=${status}` : '')).items) } catch (reason) { setError(reason.message) }
  }

  async function groupAction(label, callback, refresh) {
    setBusy(label); setError('')
    try { await callback(); setNotice(`${label} completed.`); await refresh() } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  return <section className="documents-workspace">
    <header className="section-heading">
      <div><h2>Quality &amp; Approval</h2><p>Unified review queue, quality gates, duplicate/conflict resolution, and per-target-use approval across every governed entity type.</p></div>
      <button onClick={() => loadQueue()}>Refresh queue</button>
    </header>
    <div className="dataset-tabs">{tabs.map((value) => <button key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>{value}</button>)}</div>
    {notice && <div className="success-note" role="status">{notice}</div>}
    {error && <div className="form-error" role="alert">{error}</div>}

    {tab === 'Overview' && <OverviewTab queueCounts={queueCounts} queueItems={queueItems} />}

    {tab === 'Queue' && <QueueTab
      queueItems={queueItems} queueFilters={queueFilters}
      setQueueFilters={(f) => { setQueueFilters(f); loadQueue(f) }}
      openReview={openReview}
      openNew={(body) => reviewAction('Review item opened', async () => {
        const created = await openGovernanceReviewItem(body)
        await openReview(created.public_id)
      })}
      busy={busy}
    />}

    {tab === 'Review Detail' && <ReviewDetailTab
      reviewDetail={reviewDetail} busy={busy}
      assign={(admin) => reviewAction('Assigned', () => assignGovernanceReviewItem(selectedReviewId, admin))}
      setStatus={(status, notes) => reviewAction('Status updated', () => setGovernanceReviewItemStatus(selectedReviewId, status, notes))}
      addNote={(note) => reviewAction('Note added', () => addGovernanceReviewItemNote(selectedReviewId, note))}
    />}

    {tab === 'Quality' && <QualityTab
      entityType={entityType} setEntityType={setEntityType}
      entityPublicId={entityPublicId} setEntityPublicId={setEntityPublicId}
      busy={busy}
      assess={() => reviewAction('Quality assessed', () => assessGovernanceQuality(entityType, entityPublicId))}
    />}

    {tab === 'Duplicates' && <GroupsTab
      title="Duplicate groups" groups={duplicateGroups} busy={busy}
      resolutionActions={RESOLUTION_ACTIONS}
      load={loadDuplicates}
      syncManual={(id) => groupAction('Duplicate sync', () => syncManualDataDuplicate(id), () => loadDuplicates())}
      syncChunk={(id) => groupAction('Duplicate sync', () => syncChunkDuplicate(id), () => loadDuplicates())}
      resolve={(groupId, body) => groupAction('Duplicate resolved', () => resolveGovernanceDuplicateGroup(groupId, body), () => loadDuplicates())}
      kind="duplicate"
    />}

    {tab === 'Conflicts' && <GroupsTab
      title="Conflict groups" groups={conflictGroups} busy={busy}
      resolutionActions={RESOLUTION_ACTIONS}
      load={loadConflicts}
      syncStructuredRecord={(id) => groupAction('Conflict sync', () => syncStructuredRecordConflict(id), () => loadConflicts())}
      resolve={(groupId, body) => groupAction('Conflict resolved', () => resolveGovernanceConflictGroup(groupId, body), () => loadConflicts())}
      kind="conflict"
    />}

    {tab === 'Approvals' && <ApprovalsTab busy={busy} />}

    {tab === 'Export Readiness' && <ExportReadinessTab />}

    {tab === 'History' && <HistoryTab
      reviewHistory={reviewHistory} selectedReviewId={selectedReviewId}
      loadHistory={async () => setReviewHistory(await governanceReviewItemHistory(selectedReviewId))}
    />}
  </section>
}

function OverviewTab({ queueCounts, queueItems }) {
  return <>
    <h3>Review queue by status</h3>
    <section className="metric-grid">
      {REVIEW_STATUSES.map((status) => <article className="status-card" key={status}><span>{status.replaceAll('_', ' ')}</span><strong>{queueCounts[status] || 0}</strong></article>)}
    </section>
    <h3>Highest-priority open items</h3>
    <div className="candidate-list">
      {queueItems.slice(0, 10).map((item) => (
        <article key={item.public_id}>
          <header><strong>{item.review_code}</strong><span>{item.priority} · {item.status}</span></header>
          <p>{item.entity_type} -- {item.entity_public_id}</p>
        </article>
      ))}
    </div>
  </>
}

function QueueTab({ queueItems, queueFilters, setQueueFilters, openReview, openNew, busy }) {
  const [newEntityType, setNewEntityType] = useState('document_page')
  const [newEntityId, setNewEntityId] = useState('')
  const [newReason, setNewReason] = useState('submitted_for_review')
  const [newPriority, setNewPriority] = useState('normal')
  return <>
    <h3>Filters</h3>
    <div className="panel-controls">
      <label>Status
        <select value={queueFilters.status} onChange={(e) => setQueueFilters({ ...queueFilters, status: e.target.value })}>
          <option value="">Any</option>
          {REVIEW_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label>Priority
        <select value={queueFilters.priority} onChange={(e) => setQueueFilters({ ...queueFilters, priority: e.target.value })}>
          <option value="">Any</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      <label>Entity type
        <select value={queueFilters.entity_type} onChange={(e) => setQueueFilters({ ...queueFilters, entity_type: e.target.value })}>
          <option value="">Any</option>
          {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
    </div>
    <h3>Open items</h3>
    <div className="candidate-list">
      {queueItems.map((item) => (
        <article key={item.public_id}>
          <header><strong>{item.review_code}</strong><span>{item.priority} · {item.status}</span></header>
          <p>{item.entity_type} -- {item.entity_public_id}</p>
          <button type="button" onClick={() => openReview(item.public_id)}>Open</button>
        </article>
      ))}
    </div>
    <h3>Open a review item manually</h3>
    <div className="panel-controls">
      <label>Entity type
        <select value={newEntityType} onChange={(e) => setNewEntityType(e.target.value)}>
          {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label>Entity public id<input value={newEntityId} onChange={(e) => setNewEntityId(e.target.value)} /></label>
      <label>Priority
        <select value={newPriority} onChange={(e) => setNewPriority(e.target.value)}>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
    </div>
    <label>Reason<input value={newReason} onChange={(e) => setNewReason(e.target.value)} /></label>
    <button
      disabled={Boolean(busy) || !newEntityId.trim()}
      onClick={() => openNew({ entity_type: newEntityType, entity_public_id: newEntityId, reason: newReason, priority: newPriority })}
    >Open review item</button>
  </>
}

function ReviewDetailTab({ reviewDetail, busy, assign, setStatus, addNote }) {
  const [assignee, setAssignee] = useState('')
  const [status, setStatusValue] = useState('resolved')
  const [notes, setNotes] = useState('')
  const [note, setNote] = useState('')
  if (!reviewDetail) return <div className="notice">Open a review item from the Queue tab first.</div>
  return <>
    <h3>{reviewDetail.review_code}</h3>
    <p>{reviewDetail.entity_type} -- {reviewDetail.entity_public_id}</p>
    <p>Status: {reviewDetail.status} · Priority: {reviewDetail.priority} · Assigned to: {reviewDetail.assigned_admin_public_id || 'unassigned'}</p>

    <h4>Issues</h4>
    {!reviewDetail.issues.length ? <p>No issues recorded.</p> : (
      <ul>{reviewDetail.issues.map((issue) => (
        <li key={issue.public_id}>
          [{issue.severity}{issue.is_blocking ? ', blocking' : ''}] {issue.issue_category}: {issue.message}
          {issue.resolved_at ? ' (resolved)' : ''}
        </li>
      ))}</ul>
    )}

    <h4>Target approvals</h4>
    {!reviewDetail.target_approvals.length ? <p>No approval decisions recorded yet.</p> : (
      <ul>{reviewDetail.target_approvals.map((a) => <li key={a.public_id}>{a.target_use}: {a.decision} ({a.decision_code})</li>)}</ul>
    )}

    <h4>Assign</h4>
    <div className="panel-controls">
      <input placeholder="admin public id" value={assignee} onChange={(e) => setAssignee(e.target.value)} />
      <button disabled={Boolean(busy) || !assignee.trim()} onClick={() => assign(assignee)}>Assign</button>
    </div>

    <h4>Change status</h4>
    <div className="panel-controls">
      <select value={status} onChange={(e) => setStatusValue(e.target.value)}>
        {REVIEW_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <input placeholder="notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button disabled={Boolean(busy)} onClick={() => setStatus(status, notes)}>Update status</button>
    </div>

    <h4>Add a note</h4>
    <div className="panel-controls">
      <input value={note} onChange={(e) => setNote(e.target.value)} />
      <button disabled={Boolean(busy) || !note.trim()} onClick={() => { addNote(note); setNote('') }}>Add note</button>
    </div>
  </>
}

function QualityTab({ entityType, setEntityType, entityPublicId, setEntityPublicId, busy, assess }) {
  const [result, setResult] = useState(null)
  return <>
    <h3>Assess an entity's quality</h3>
    <p>Reads the entity's own authoritative quality result (dataset record, manual data record, or semantic chunk) and syncs any blocking issues onto its governance review item.</p>
    <div className="panel-controls">
      <label>Entity type
        <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
          {['dataset_record', 'manual_data_record', 'semantic_chunk'].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label>Entity public id<input value={entityPublicId} onChange={(e) => setEntityPublicId(e.target.value)} /></label>
    </div>
    <button
      disabled={Boolean(busy) || !entityPublicId.trim()}
      onClick={async () => setResult(await assess())}
    >Run quality assessment</button>
    {result && (
      <div className="history-panel">
        <p>Blocked: {result.normalized_quality.is_blocked ? 'yes' : 'no'}</p>
        <p>Overall score: {result.normalized_quality.overall_score}</p>
        <p>Blocking issue codes: {result.normalized_quality.blocking_issue_codes.join(', ') || 'none'}</p>
        <p>Review item: {result.review_item ? `${result.review_item.review_code} (${result.review_item.status})` : 'none opened'}</p>
      </div>
    )}
  </>
}

function GroupsTab({ title, groups, busy, resolutionActions, load, syncManual, syncChunk, syncStructuredRecord, resolve, kind }) {
  const [statusFilter, setStatusFilter] = useState('')
  const [entityId, setEntityId] = useState('')
  const [resolutionAction, setResolutionAction] = useState(resolutionActions[0])
  const [resolutionReason, setResolutionReason] = useState('')
  useEffect(() => { load(statusFilter) }, [])
  return <>
    <h3>{title}</h3>
    <div className="panel-controls">
      <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); load(e.target.value) }}>
        <option value="">Any status</option>
        <option value="open">open</option>
        <option value="resolved">resolved</option>
      </select>
      <button type="button" onClick={() => load(statusFilter)}>Refresh</button>
    </div>

    {kind === 'duplicate' && (
      <>
        <h4>Run a duplicate check</h4>
        <div className="panel-controls">
          <input placeholder="entity public id" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
          <button disabled={Boolean(busy) || !entityId.trim()} onClick={() => syncManual(entityId)}>Sync (manual data record)</button>
          <button disabled={Boolean(busy) || !entityId.trim()} onClick={() => syncChunk(entityId)}>Sync (semantic chunk)</button>
        </div>
      </>
    )}
    {kind === 'conflict' && (
      <>
        <h4>Run a conflict check</h4>
        <div className="panel-controls">
          <input placeholder="structured record candidate public id" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
          <button disabled={Boolean(busy) || !entityId.trim()} onClick={() => syncStructuredRecord(entityId)}>Sync (structured record)</button>
        </div>
      </>
    )}

    <div className="candidate-list">
      {groups.map((group) => (
        <article key={group.public_id}>
          <header><strong>{group.group_code}</strong><span>{group.status}</span></header>
          <p>{group.duplicate_type || group.conflict_type} -- {group.match_reason}</p>
          <ul>{(group.members || []).map((m) => <li key={`${m.entity_type}-${m.entity_public_id}`}>{m.role}: {m.entity_type} {m.entity_public_id}</li>)}</ul>
          {group.status === 'open' && (
            <div className="panel-controls">
              <select value={resolutionAction} onChange={(e) => setResolutionAction(e.target.value)}>
                {resolutionActions.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <input placeholder="resolution reason" value={resolutionReason} onChange={(e) => setResolutionReason(e.target.value)} />
              <button
                disabled={Boolean(busy) || !resolutionReason.trim()}
                onClick={() => resolve(group.public_id, { resolution_action: resolutionAction, resolution_reason: resolutionReason })}
              >Resolve</button>
            </div>
          )}
        </article>
      ))}
    </div>
  </>
}

function ApprovalsTab({ busy }) {
  const [entityType, setEntityType] = useState('manual_data_record')
  const [entityId, setEntityId] = useState('')
  const [targetUse, setTargetUse] = useState('training')
  const [matrix, setMatrix] = useState(null)
  const [overrideDecision, setOverrideDecision] = useState('allowed')
  const [overrideReason, setOverrideReason] = useState('')
  const [lastDecision, setLastDecision] = useState(null)

  async function loadMatrix() { setMatrix(await governanceApprovalStatus(entityType, entityId)) }

  return <>
    <h3>Per-target-use approval matrix</h3>
    <div className="panel-controls">
      <label>Entity type
        <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
          {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label>Entity public id<input value={entityId} onChange={(e) => setEntityId(e.target.value)} /></label>
      <button disabled={!entityId.trim()} type="button" onClick={loadMatrix}>Load matrix</button>
    </div>
    {matrix && (
      <table>
        <thead><tr><th>Target use</th><th>Decision</th><th>Code</th><th>Expired</th></tr></thead>
        <tbody>
          {TARGET_USES.map((use) => (
            <tr key={use}>
              <td>{use}</td>
              <td>{matrix.targets[use]?.decision}</td>
              <td>{matrix.targets[use]?.decision_code}</td>
              <td>{matrix.targets[use]?.expired ? 'yes' : 'no'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )}

    <h3>Evaluate a target use</h3>
    <div className="panel-controls">
      <select value={targetUse} onChange={(e) => setTargetUse(e.target.value)}>
        {TARGET_USES.map((u) => <option key={u} value={u}>{u}</option>)}
      </select>
      <button
        disabled={Boolean(busy) || !entityId.trim()}
        onClick={async () => { setLastDecision(await evaluateGovernanceApproval(entityType, entityId, targetUse)); await loadMatrix() }}
      >Evaluate</button>
    </div>
    {lastDecision && <p>Decision: {lastDecision.decision} ({lastDecision.decision_code})</p>}

    <h3>Admin override</h3>
    <p>Always requires an explicit reason -- overrides are audited and never silently applied.</p>
    <div className="panel-controls">
      <select value={overrideDecision} onChange={(e) => setOverrideDecision(e.target.value)}>
        <option value="allowed">allowed</option>
        <option value="blocked">blocked</option>
        <option value="needs_review">needs_review</option>
      </select>
      <input placeholder="override reason (required)" value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} />
      <button
        disabled={Boolean(busy) || !entityId.trim() || !overrideReason.trim()}
        onClick={async () => {
          setLastDecision(await overrideGovernanceApproval(entityType, entityId, targetUse, { decision: overrideDecision, reason: overrideReason }))
          await loadMatrix()
        }}
      >Override</button>
    </div>
  </>
}

function ExportReadinessTab() {
  const [entityType, setEntityType] = useState('structured_record_candidate')
  const [entityId, setEntityId] = useState('')
  const [targetUse, setTargetUse] = useState('dataset_export')
  const [result, setResult] = useState(null)
  const [checkError, setCheckError] = useState('')
  return <>
    <h3>Export / RAG-handoff readiness check</h3>
    <p>Read-only preflight -- the same check the export and RAG handoff actions run before proceeding.</p>
    <div className="panel-controls">
      <label>Entity type
        <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
          {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label>Entity public id<input value={entityId} onChange={(e) => setEntityId(e.target.value)} /></label>
      <label>Target use
        <select value={targetUse} onChange={(e) => setTargetUse(e.target.value)}>
          <option value="dataset_export">dataset_export</option>
          <option value="rag_handoff">rag_handoff</option>
        </select>
      </label>
    </div>
    <button
      disabled={!entityId.trim()}
      onClick={async () => {
        setCheckError('')
        try { setResult(await governanceExportReadiness(entityType, entityId, targetUse)) } catch (reason) { setCheckError(reason.message) }
      }}
    >Check readiness</button>
    {checkError && <div className="form-error" role="alert">{checkError}</div>}
    {result && (
      <div className="history-panel">
        <p>Decision: {result.decision} ({result.decision_code})</p>
        <p>Blocking issue ids: {result.blocking_issue_ids.join(', ') || 'none'}</p>
        <p>Required actions: {result.required_actions.join('; ') || 'none'}</p>
      </div>
    )}
  </>
}

function HistoryTab({ reviewHistory, selectedReviewId, loadHistory }) {
  if (!selectedReviewId) return <div className="notice">Open a review item from the Queue tab first.</div>
  return <>
    <h3>Review item history</h3>
    <button type="button" onClick={loadHistory}>Load history</button>
    {reviewHistory && (
      <ol>{reviewHistory.items.map((e) => <li key={e.public_id}>{e.event_type} by {e.performed_by_admin_public_id} at {e.created_at}{e.notes ? ` -- ${e.notes}` : ''}</li>)}</ol>
    )}
  </>
}
