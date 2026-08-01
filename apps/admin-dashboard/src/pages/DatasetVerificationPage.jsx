import { useEffect, useState } from 'react'
import {
  verificationCases, createVerificationCase, verificationCase, startVerificationCase,
  cancelVerificationCase, verificationEvidence, collectVerificationEvidence,
  addManualVerificationEvidence, refreshVerificationEvidence, verificationIdentity,
  assessVerificationIdentity, recordManualIdentitySignal, assessVerificationLicence,
  verificationTerms, verificationPermissions, verificationPermissionReviews,
  assessVerificationPermissions, assessVerificationCommercialUse, reviewVerificationPermission,
  verificationUpstreams, addVerificationUpstream, verifyVerificationUpstream,
  verificationConflicts, detectVerificationConflicts, resolveVerificationConflict,
  finalizeVerificationCase, verificationReport, reverifyVerificationCase,
  verificationWithdrawalNotices, recordVerificationWithdrawalNotice, verificationEvents,
  verificationExistingSource, draftVerificationSourceRightsProposal,
} from '../services/api.js'

const TABS = [
  'Overview', 'Verification Cases', 'Evidence', 'Identity', 'Licence & Terms',
  'Permissions', 'Upstream Sources', 'Conflicts', 'Review', 'Final Report', 'History',
]

const EVIDENCE_TYPES = [
  'official_dataset_page', 'dataset_card', 'licence_file', 'licence_url',
  'repository_licence_metadata', 'terms_of_use', 'privacy_policy', 'consent_statement',
  'upstream_source', 'citation_file', 'readme', 'provider_api_metadata',
  'government_notice', 'institutional_policy', 'manual_admin_evidence',
]
const AUTHORITY_LEVELS = [
  'primary', 'official_supporting', 'secondary', 'provider_declared',
  'community_supplied', 'manual_unverified',
]
const PERMISSION_TYPES = [
  'rag_use', 'training_use', 'evaluation_use', 'commercial_use', 'redistribution',
  'modification', 'derivative_works', 'attribution_required', 'share_alike_required',
  'notice_required', 'source_disclosure_required', 'personal_data_restriction',
  'research_only', 'non_commercial_only', 'geographic_restriction', 'gated_access_restriction',
]
const ADMIN_ONLY_STATUSES = ['approved', 'approved_with_conditions', 'not_approved', 'prohibited']
const UPSTREAM_RELATIONSHIP_TYPES = [
  'derived_from', 'aggregated_from', 'mirrored_from', 'translated_from',
  'annotated_from', 'converted_from', 'subset_of', 'unknown',
]
const UPSTREAM_VERIFICATION_STATUSES = ['not_verified', 'partial', 'verified', 'conflicting']
const WITHDRAWAL_NOTICE_TYPES = [
  'dataset_withdrawn', 'licence_changed', 'terms_changed', 'rights_holder_request',
  'privacy_request', 'provider_removed', 'other',
]
const COMMERCIAL_USE_CATEGORIES = [
  'internal_testing', 'research', 'free_public_service', 'paid_commercial_product',
  'redistributed_dataset', 'commercial_training_deployment',
]
const CONFLICT_RESOLUTION_STATUSES = ['resolved', 'accepted_risk', 'dismissed']

const SAFETY_NOTICE = 'Dataset verification only ever produces an evidence-backed record for human review -- nothing here downloads a dataset payload file, imports records, activates RAG, creates a training dataset version, starts training, or releases a model. Declared metadata alone is never enough for an approved status; only an explicit human Admin review can approve, deny, or prohibit a permission.'

const emptyManualEvidence = { evidence_type: 'licence_file', content_text: '', source_url: '', authority_level: 'manual_unverified' }
const emptyCollectEvidence = { evidence_type: 'licence_file', source_url: '', authority_level: '' }
const emptyUpstream = { upstream_name: '', upstream_url: '', upstream_organization: '', upstream_licence: '', relationship_type: 'unknown', coverage_notes: '' }
const emptyWithdrawal = { notice_type: 'licence_changed', source_url: '', notice_text: '' }
const emptyManualSignal = { signal_type: 'dataset_card_identifier', expected_value: '', observed_value: '', matched: false, reason: '' }

export default function DatasetVerificationPage({ initialCandidatePublicId, onOpenSampleImport }) {
  const [tab, setTab] = useState('Overview')
  const [cases, setCases] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [newCandidateId, setNewCandidateId] = useState(initialCandidatePublicId || '')
  const [selectedId, setSelectedId] = useState('')
  const [selected, setSelected] = useState(null)

  const [evidenceItems, setEvidenceItems] = useState([])
  const [manualEvidence, setManualEvidence] = useState(emptyManualEvidence)
  const [collectEvidence, setCollectEvidenceForm] = useState(emptyCollectEvidence)

  const [identityChecks, setIdentityChecks] = useState([])
  const [manualSignal, setManualSignal] = useState(emptyManualSignal)

  const [termsSummary, setTermsSummary] = useState(null)

  const [permissions, setPermissions] = useState([])
  const [reviews, setReviews] = useState([])
  const [commercialCategory, setCommercialCategory] = useState('research')
  const [reviewDrafts, setReviewDrafts] = useState({})

  const [upstreams, setUpstreams] = useState([])
  const [newUpstream, setNewUpstream] = useState(emptyUpstream)

  const [conflicts, setConflicts] = useState([])
  const [resolveDrafts, setResolveDrafts] = useState({})

  const [report, setReport] = useState(null)
  const [existingSource, setExistingSource] = useState(undefined)
  const [sourceRightsResult, setSourceRightsResult] = useState(null)
  const [withdrawals, setWithdrawals] = useState([])
  const [newWithdrawal, setNewWithdrawal] = useState(emptyWithdrawal)
  const [events, setEvents] = useState([])

  function loadCases() {
    verificationCases('?page_size=100').then((data) => setCases(data.items)).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadCases() }, [])

  useEffect(() => {
    if (!initialCandidatePublicId) return
    verificationCases(`?candidate_public_id=${initialCandidatePublicId}&page_size=1`)
      .then((data) => { if (data.items.length > 0) selectCase(data.items[0].public_id) })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCandidatePublicId])

  function selectCase(publicId) {
    setSelectedId(publicId)
    setSelected(null)
    setError(''); setNotice('')
    refreshSelected(publicId)
    setTab('Evidence')
  }

  function refreshSelected(publicId = selectedId) {
    if (!publicId) return
    verificationCase(publicId).then(setSelected).catch((reason) => setError(reason.message))
    verificationEvidence(publicId).then((data) => setEvidenceItems(data.items)).catch(() => {})
    verificationIdentity(publicId).then((data) => setIdentityChecks(data.items)).catch(() => {})
    verificationTerms(publicId).then(setTermsSummary).catch(() => {})
    verificationPermissions(publicId).then((data) => setPermissions(data.items)).catch(() => {})
    verificationPermissionReviews(publicId).then((data) => setReviews(data.items)).catch(() => {})
    verificationUpstreams(publicId).then((data) => setUpstreams(data.items)).catch(() => {})
    verificationConflicts(publicId).then((data) => setConflicts(data.items)).catch(() => {})
    verificationWithdrawalNotices(publicId).then((data) => setWithdrawals(data.items)).catch(() => {})
    verificationEvents(publicId).then((data) => setEvents(data.items)).catch(() => {})
    verificationReport(publicId).then(setReport).catch(() => setReport(null))
    verificationExistingSource(publicId).then((data) => setExistingSource(data.existing_source)).catch(() => setExistingSource(undefined))
  }

  async function action(label, fn) {
    setBusy(label); setError(''); setNotice('')
    try {
      await fn()
      loadCases()
      refreshSelected()
      setNotice(`${label}: done.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitNewCase(event) {
    event.preventDefault()
    if (!newCandidateId.trim()) return
    setBusy('Create case'); setError('')
    try {
      const created = await createVerificationCase({ candidate_public_id: newCandidateId.trim() })
      loadCases()
      selectCase(created.public_id)
      setNotice(`Verification case ${created.verification_code} created.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitManualEvidence(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Add manual evidence', async () => {
      await addManualVerificationEvidence(selectedId, manualEvidence)
      setManualEvidence(emptyManualEvidence)
    })
  }

  async function submitCollectEvidence(event) {
    event.preventDefault()
    if (!selectedId) return
    const payload = { ...collectEvidence, authority_level: collectEvidence.authority_level || null }
    action('Collect evidence', async () => {
      await collectVerificationEvidence(selectedId, payload)
      setCollectEvidenceForm(emptyCollectEvidence)
    })
  }

  async function submitManualSignal(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Record manual identity signal', async () => {
      await recordManualIdentitySignal(selectedId, manualSignal)
      setManualSignal(emptyManualSignal)
    })
  }

  async function submitReview(permissionType) {
    const draft = reviewDrafts[permissionType] || {}
    if (!draft.status || !draft.reason?.trim()) { setError('A status and a non-empty reason are required to review a permission.'); return }
    action(`Review ${permissionType}`, () => reviewVerificationPermission(selectedId, permissionType, { status: draft.status, reason: draft.reason, conditions: {} }))
  }

  async function submitUpstream(event) {
    event.preventDefault()
    if (!selectedId || !newUpstream.upstream_name.trim()) return
    action('Add upstream source', async () => {
      await addVerificationUpstream(selectedId, newUpstream)
      setNewUpstream(emptyUpstream)
    })
  }

  async function submitResolveConflict(conflictId) {
    const draft = resolveDrafts[conflictId] || {}
    if (!draft.resolution_status || !draft.resolution_reason?.trim()) { setError('A resolution status and a non-empty reason are required.'); return }
    action('Resolve conflict', () => resolveVerificationConflict(selectedId, conflictId, draft))
  }

  async function submitWithdrawal(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Record withdrawal notice', async () => {
      await recordVerificationWithdrawalNotice(selectedId, newWithdrawal)
      setNewWithdrawal(emptyWithdrawal)
    })
  }

  async function submitDraftSourceRightsProposal() {
    setBusy('Draft Source & Rights proposal'); setError(''); setNotice('')
    try {
      const result = await draftVerificationSourceRightsProposal(selectedId)
      setSourceRightsResult(result)
      setNotice(result.drafted ? 'Source & Rights proposal drafted -- review it in Admin Review before it takes effect.' : result.reason)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  const permissionByType = Object.fromEntries(permissions.map((p) => [p.permission_type, p]))

  const currentPage = <>
    <section className="intro">
      <div><span>Data research studio</span><h2>Dataset Verification</h2></div>
      <div className="phase-number">P11</div>
    </section>
    <div className="notice">{SAFETY_NOTICE}</div>
    {error && <div className="notice error-notice">{error}</div>}
    {notice && <div className="success-note">{notice}</div>}
    <nav aria-label="Dataset Verification sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Overview' && <>
      <h3>What this workspace does</h3>
      <p>Verify a Phase 10 candidate&apos;s identity, official source, dataset card, declared/verified licence, terms, privacy/consent, upstream sources, and independently-assessed RAG/training/evaluation/commercial-use permissions. Nothing here is ever auto-approved -- every permission requires an explicit human Admin decision.</p>
      {selected && <div className="notice" style={{ marginTop: '1rem' }}>
        <h4>{selected.verification_code}</h4>
        <p>Status: <strong>{selected.status}</strong> · Identity: <strong>{selected.identity_status}</strong> · Licence: <strong>{selected.licence_status}</strong></p>
        <p>Evidence: <strong>{selected.evidence_status}</strong> · Terms: <strong>{selected.terms_status}</strong> · Upstream: <strong>{selected.upstream_status}</strong> · Permissions: <strong>{selected.permission_status}</strong></p>
        <p>Conflicts: <strong>{selected.conflict_count}</strong> · Reverification: <strong>{selected.verification_expiry_status}</strong></p>
      </div>}
      {!selected && <p>Select or create a verification case in the &quot;Verification Cases&quot; tab to get started.</p>}
    </>}

    {tab === 'Verification Cases' && <>
      <h3>Verification cases</h3>
      <form onSubmit={submitNewCase} style={{ display: 'flex', gap: '.5rem', alignItems: 'flex-end', margin: '1rem 0' }}>
        <label>Phase 10 candidate public ID<input required value={newCandidateId} onChange={(e) => setNewCandidateId(e.target.value)} placeholder="candidate public_id" /></label>
        <button type="submit" disabled={!!busy}>Start licence verification</button>
      </form>
      <table>
        <thead><tr><th>Code</th><th>Status</th><th>Licence</th><th>Permissions</th><th>Conflicts</th><th></th></tr></thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.public_id}>
              <td>{item.verification_code}</td>
              <td>{item.status}</td>
              <td>{item.licence_status}</td>
              <td>{item.permission_status}</td>
              <td>{item.conflict_count}</td>
              <td>
                <button onClick={() => selectCase(item.public_id)}>Open</button>
                {item.status === 'draft' && <button disabled={!!busy} onClick={() => action('Start case', () => startVerificationCase(item.public_id))}>Start</button>}
                {item.locked_at === null && <button disabled={!!busy} onClick={() => action('Cancel case', () => cancelVerificationCase(item.public_id))}>Cancel</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>}

    {tab === 'Evidence' && <>
      <h3>Evidence{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <table>
          <thead><tr><th>Type</th><th>Authority</th><th>Retrieval</th><th>Current</th><th>Checksum</th><th>Excerpt</th><th></th></tr></thead>
          <tbody>
            {evidenceItems.map((e) => (
              <tr key={e.public_id}>
                <td>{e.evidence_type}</td>
                <td>{e.authority_level}</td>
                <td>{e.retrieval_status}</td>
                <td>{e.is_current ? 'yes' : 'superseded'}</td>
                <td><small>{e.content_checksum?.slice(0, 12)}…</small></td>
                <td style={{ maxWidth: '20rem' }}>{e.content_excerpt}</td>
                <td>{e.source_url && e.is_current && <button disabled={!!busy} onClick={() => action('Refresh evidence', () => refreshVerificationEvidence(selectedId, e.public_id))}>Refresh</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h4 style={{ marginTop: '1.5rem' }}>Collect evidence from a registered/approved domain</h4>
        <form onSubmit={submitCollectEvidence} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
          <label>Evidence type
            <select value={collectEvidence.evidence_type} onChange={(e) => setCollectEvidenceForm({ ...collectEvidence, evidence_type: e.target.value })}>
              {EVIDENCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Source URL<input required value={collectEvidence.source_url} onChange={(e) => setCollectEvidenceForm({ ...collectEvidence, source_url: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Collect evidence</button>
        </form>

        <h4 style={{ marginTop: '1.5rem' }}>Add manual evidence text</h4>
        <form onSubmit={submitManualEvidence} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
          <label>Evidence type
            <select value={manualEvidence.evidence_type} onChange={(e) => setManualEvidence({ ...manualEvidence, evidence_type: e.target.value })}>
              {EVIDENCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Authority level
            <select value={manualEvidence.authority_level} onChange={(e) => setManualEvidence({ ...manualEvidence, authority_level: e.target.value })}>
              {AUTHORITY_LEVELS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>
          <label>Source URL (optional)<input value={manualEvidence.source_url} onChange={(e) => setManualEvidence({ ...manualEvidence, source_url: e.target.value })} /></label>
          <label>Text<textarea required rows={4} value={manualEvidence.content_text} onChange={(e) => setManualEvidence({ ...manualEvidence, content_text: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Add manual evidence</button>
        </form>
      </>}
    </>}

    {tab === 'Identity' && <>
      <h3>Identity{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <p>Identity status: <strong>{selected.identity_status}</strong>. Title similarity alone can never reach &quot;verified&quot; -- only an exact provider ID or exact official-domain match can.</p>
        <button disabled={!!busy} onClick={() => action('Assess identity', () => assessVerificationIdentity(selectedId))}>Run automated identity assessment</button>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Signal</th><th>Expected</th><th>Observed</th><th>Matched</th><th>Reason</th></tr></thead>
          <tbody>
            {identityChecks.map((c) => (
              <tr key={c.public_id}><td>{c.signal_type}</td><td>{c.expected_value || '—'}</td><td>{c.observed_value || '—'}</td><td>{c.matched ? 'yes' : 'no'}</td><td>{c.reason}</td></tr>
            ))}
          </tbody>
        </table>

        <h4 style={{ marginTop: '1.5rem' }}>Record a manual signal</h4>
        <form onSubmit={submitManualSignal} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
          <label>Signal type<input value={manualSignal.signal_type} onChange={(e) => setManualSignal({ ...manualSignal, signal_type: e.target.value })} /></label>
          <label>Expected value<input value={manualSignal.expected_value} onChange={(e) => setManualSignal({ ...manualSignal, expected_value: e.target.value })} /></label>
          <label>Observed value<input value={manualSignal.observed_value} onChange={(e) => setManualSignal({ ...manualSignal, observed_value: e.target.value })} /></label>
          <label><input type="checkbox" checked={manualSignal.matched} onChange={(e) => setManualSignal({ ...manualSignal, matched: e.target.checked })} /> Matched</label>
          <label>Reason<textarea required rows={2} value={manualSignal.reason} onChange={(e) => setManualSignal({ ...manualSignal, reason: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Record signal</button>
        </form>
      </>}
    </>}

    {tab === 'Licence & Terms' && <>
      <h3>Licence &amp; Terms{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <p>Declared licence: <strong>{selected.declared_licence || 'none declared'}</strong></p>
        <p>Normalized (SPDX, evidence-derived only): <strong>{selected.normalized_licence_identifier || 'not recognized'}</strong></p>
        <p>Licence status: <strong>{selected.licence_status}</strong></p>
        <button disabled={!!busy} onClick={() => action('Assess licence', () => assessVerificationLicence(selectedId))}>Run licence normalization</button>

        <h4 style={{ marginTop: '1.5rem' }}>Terms/privacy/consent snapshot completeness</h4>
        <p>Terms status: <strong>{selected.terms_status}</strong></p>
        {termsSummary && Object.entries(termsSummary.by_evidence_type || {}).map(([evidenceType, items]) => (
          <p key={evidenceType}>{evidenceType}: {items.length} snapshot(s)</p>
        ))}
      </>}
    </>}

    {tab === 'Permissions' && <>
      <h3>Permissions{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <button disabled={!!busy} onClick={() => action('Assess permissions', () => assessVerificationPermissions(selectedId))}>Run automated permission assessment</button>
        <div style={{ display: 'flex', gap: '.5rem', alignItems: 'flex-end', margin: '1rem 0' }}>
          <label>Commercial intended use
            <select value={commercialCategory} onChange={(e) => setCommercialCategory(e.target.value)}>
              {COMMERCIAL_USE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <button disabled={!!busy} onClick={() => action('Assess commercial use', () => assessVerificationCommercialUse(selectedId, { intended_use_category: commercialCategory }))}>Assess commercial use</button>
        </div>

        <table>
          <thead><tr><th>Permission</th><th>Automated assessment</th><th>Admin decision</th><th>Decision basis</th><th>Review</th></tr></thead>
          <tbody>
            {PERMISSION_TYPES.map((permissionType) => {
              const row = permissionByType[permissionType]
              const draft = reviewDrafts[permissionType] || { status: 'approved', reason: '' }
              return (
                <tr key={permissionType}>
                  <td>{permissionType}</td>
                  <td>{row ? row.status : 'not yet assessed'}</td>
                  <td>{row?.reviewed_by ? `${row.status} (by ${row.reviewed_by})` : 'no Admin decision yet'}</td>
                  <td style={{ maxWidth: '16rem' }}>{row?.decision_basis}</td>
                  <td>
                    <select value={draft.status} onChange={(e) => setReviewDrafts({ ...reviewDrafts, [permissionType]: { ...draft, status: e.target.value } })}>
                      {ADMIN_ONLY_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <input placeholder="reason (required)" value={draft.reason} onChange={(e) => setReviewDrafts({ ...reviewDrafts, [permissionType]: { ...draft, reason: e.target.value } })} style={{ width: '10rem', marginLeft: '.25rem' }} />
                    <button disabled={!!busy || !row} onClick={() => submitReview(permissionType)} style={{ marginLeft: '.25rem' }}>Submit review</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Upstream Sources' && <>
      <h3>Upstream Sources{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <p>Upstream status: <strong>{selected.upstream_status}</strong>. While any upstream source remains unresolved, training/commercial permission stays capped at needs_legal_review.</p>
        <table>
          <thead><tr><th>Name</th><th>Relationship</th><th>Verification</th><th></th></tr></thead>
          <tbody>
            {upstreams.map((u) => (
              <tr key={u.public_id}>
                <td>{u.upstream_name}</td>
                <td>{u.relationship_type}</td>
                <td>{u.verification_status}</td>
                <td>
                  <select defaultValue={u.verification_status} onChange={(e) => action('Verify upstream', () => verifyVerificationUpstream(selectedId, u.public_id, { verification_status: e.target.value }))} disabled={!!busy}>
                    {UPSTREAM_VERIFICATION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <h4 style={{ marginTop: '1.5rem' }}>Add an upstream source</h4>
        <form onSubmit={submitUpstream} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
          <label>Name<input required value={newUpstream.upstream_name} onChange={(e) => setNewUpstream({ ...newUpstream, upstream_name: e.target.value })} /></label>
          <label>URL<input value={newUpstream.upstream_url} onChange={(e) => setNewUpstream({ ...newUpstream, upstream_url: e.target.value })} /></label>
          <label>Relationship type
            <select value={newUpstream.relationship_type} onChange={(e) => setNewUpstream({ ...newUpstream, relationship_type: e.target.value })}>
              {UPSTREAM_RELATIONSHIP_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <button type="submit" disabled={!!busy}>Add upstream source</button>
        </form>
      </>}
    </>}

    {tab === 'Conflicts' && <>
      <h3>Conflicts{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <button disabled={!!busy} onClick={() => action('Detect conflicts', () => detectVerificationConflicts(selectedId))}>Run conflict detection</button>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Type</th><th>Severity</th><th>Resolution</th><th>Summary</th><th></th></tr></thead>
          <tbody>
            {conflicts.map((c) => {
              const draft = resolveDrafts[c.public_id] || { resolution_status: 'resolved', resolution_reason: '' }
              const unresolved = c.resolution_status === 'unresolved'
              return (
                <tr key={c.public_id}>
                  <td>{c.conflict_type}</td>
                  <td>{c.conflict_severity}</td>
                  <td>{c.resolution_status}</td>
                  <td style={{ maxWidth: '18rem' }}>{c.summary}</td>
                  <td>
                    {unresolved && <>
                      <select value={draft.resolution_status} onChange={(e) => setResolveDrafts({ ...resolveDrafts, [c.public_id]: { ...draft, resolution_status: e.target.value } })}>
                        {CONFLICT_RESOLUTION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                      <input placeholder="reason (required)" value={draft.resolution_reason} onChange={(e) => setResolveDrafts({ ...resolveDrafts, [c.public_id]: { ...draft, resolution_reason: e.target.value } })} style={{ width: '10rem', marginLeft: '.25rem' }} />
                      <button disabled={!!busy} onClick={() => submitResolveConflict(c.public_id)} style={{ marginLeft: '.25rem' }}>Resolve</button>
                    </>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Review' && <>
      <h3>Human review workflow{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <p>Workflow: collect evidence → verify identity → review licence/terms → review upstream sources → run automated permission assessment → resolve conflicts → Admin review (use the Permissions tab) → finalize report.</p>
        <h4>Review history (append-only)</h4>
        <table>
          <thead><tr><th>Permission</th><th>Decision</th><th>Reviewer</th><th>Reason</th><th>Reviewed at</th></tr></thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.public_id}><td>{r.permission_type}</td><td>{r.decision}</td><td>{r.reviewer_admin_public_id}</td><td>{r.reason}</td><td>{r.reviewed_at}</td></tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Final Report' && <>
      <h3>Final Report{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        {selected.locked_at === null && <>
          <p>Not finalized yet. Finalizing requires no unresolved blocking conflict and no stale reviewed evidence.</p>
          <button disabled={!!busy} onClick={() => action('Finalize', () => finalizeVerificationCase(selectedId))}>Finalize verification report</button>
        </>}
        {selected.locked_at !== null && report && <div className="notice">
          <p>Finalized at <strong>{selected.locked_at}</strong> with status <strong>{report.status}</strong>.</p>
          <table>
            <thead><tr><th>Field</th><th>Value</th><th>Provenance</th></tr></thead>
            <tbody>
              {Object.entries(report.report || {}).map(([field, entry]) => (
                <tr key={field}><td>{field.replaceAll('_', ' ')}</td><td style={{ maxWidth: '24rem' }}>{JSON.stringify(entry.value)}</td><td>{entry.provenance}</td></tr>
              ))}
            </tbody>
          </table>
        </div>}
        <h4 style={{ marginTop: '1.5rem' }}>Reverification</h4>
        <p>Expiry status: <strong>{selected.verification_expiry_status}</strong>. Works even on an already-finalized case.</p>
        <button disabled={!!busy} onClick={() => action('Reverify', () => reverifyVerificationCase(selectedId))}>Re-check evidence now</button>

        {selected.locked_at !== null && <>
          <h4 style={{ marginTop: '1.5rem' }}>Source &amp; Rights Registry</h4>
          <p>Never written to directly -- this only ever drafts a proposal through the existing Admin Assistant review pipeline. {existingSource ? `An existing data source (${existingSource.public_id}) was found matching this candidate.` : 'No existing data source matches this candidate yet.'}</p>
          <button disabled={!!busy} onClick={submitDraftSourceRightsProposal}>Draft Source &amp; Rights linking proposal</button>
          {sourceRightsResult && <p>{sourceRightsResult.drafted ? `Proposal ${sourceRightsResult.proposal.public_id} drafted (status: ${sourceRightsResult.proposal.status}). Review it on the Admin Assistant page.` : sourceRightsResult.reason}</p>}
        </>}

        {selected.locked_at !== null && onOpenSampleImport && <>
          <h4 style={{ marginTop: '1.5rem' }}>Sample Import &amp; Quarantine (Phase 12)</h4>
          <p>A finalized verification case only means the licence/rights were checked -- it never means any file was downloaded. A sample import is a separate, explicitly bound approval with its own record/byte limits and expiry.</p>
          <button disabled={!!busy} onClick={() => onOpenSampleImport(selected.public_id)}>Create Sample Import Proposal</button>
          <button disabled={!!busy} onClick={() => onOpenSampleImport(selected.public_id)} style={{ marginLeft: '.5rem' }}>Open Existing Sample Import</button>
        </>}
      </>}
    </>}

    {tab === 'History' && <>
      <h3>History{selected ? ` — ${selected.verification_code}` : ''}</h3>
      {!selected && <p>Select a verification case first.</p>}
      {selected && <>
        <h4>Withdrawal notices</h4>
        <table>
          <thead><tr><th>Type</th><th>Impact</th><th>Recorded at</th></tr></thead>
          <tbody>
            {withdrawals.map((w) => (
              <tr key={w.public_id}><td>{w.notice_type}</td><td>{w.impact_status}</td><td>{w.received_at}</td></tr>
            ))}
          </tbody>
        </table>
        <form onSubmit={submitWithdrawal} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem', marginTop: '1rem' }}>
          <label>Notice type
            <select value={newWithdrawal.notice_type} onChange={(e) => setNewWithdrawal({ ...newWithdrawal, notice_type: e.target.value })}>
              {WITHDRAWAL_NOTICE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Notice text<textarea rows={2} value={newWithdrawal.notice_text} onChange={(e) => setNewWithdrawal({ ...newWithdrawal, notice_text: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Record withdrawal notice</button>
        </form>

        <h4 style={{ marginTop: '1.5rem' }}>Events</h4>
        <div className="audit-list">
          {events.map((event) => (
            <article key={event.public_id}>
              <div><strong>{event.event_type.replaceAll('_', ' ')}</strong><span>{event.performed_by_admin_public_id}</span></div>
              <small>{event.summary} — {event.created_at}</small>
            </article>
          ))}
        </div>
      </>}
    </>}
  </>

  return currentPage
}
