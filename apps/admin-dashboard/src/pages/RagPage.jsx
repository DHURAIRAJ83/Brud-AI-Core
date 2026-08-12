import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateRagKeywordIndex,
  activateRagRetrievalProfile,
  activateRagVectorIndex,
  addRagEvaluationFixture,
  buildRagKeywordIndex,
  buildRagVectorIndex,
  closeRagChatLabSession,
  createRagChatLabSession,
  createRagChunkSet,
  createRagEmbeddingModel,
  createRagEmbeddingRun,
  createRagEvaluationRun,
  createRagEvaluationSuite,
  createRagIndexComparison,
  createRagKeywordIndex,
  createRagRetrievalProfile,
  createRagSource,
  createRagSourceVersion,
  createRagSpace,
  createRagVectorIndex,
  deactivateRagRetrievalProfile,
  executeRagEmbeddingRun,
  executeRagEvaluationRun,
  generateRagManifest,
  miniBrainDefaultRetrievalProfile,
  miniBrainSetDefaultRetrievalProfile,
  patchRagSource,
  postRagChatLabMessage,
  ragChunks,
  ragChunkSet,
  ragEmbeddingModels,
  ragEmbeddingRun,
  ragEvaluationMetrics,
  ragEvaluationSuites,
  ragGroundedAnswer,
  ragKeywordIndex,
  ragLatestVectorIndexForSpace,
  ragRetrievalProfiles,
  ragRetrieve,
  ragSources,
  ragSourceVersions,
  ragSpaces,
  ragVectorIndex,
  validateRagChunkSet,
  validateRagKeywordIndex,
  validateRagRetrievalProfile,
  validateRagSourceVersion,
  validateRagVectorIndex,
  verifyRagManifest,
} from '../services/api.js'

const RAG_NOTICE = 'Retrieval and grounded generation do not guarantee factual correctness. This is an admin-only diagnostic and evaluation workspace -- it does not affect the public chatbot.'
const DIAGNOSTIC_DISCLAIMER = 'Admin-only grounded diagnostic. This is not the public chatbot.'
const INJECTION_NOTICE = 'Chunks flagged as a possible prompt-injection attempt are structurally excluded from every embedding run and keyword index -- they can never enter a retrieved context.'
const NO_PUBLIC_ACTIVATION_NOTICE = 'Phase 16 does not add any path to public-chat activation. The public chatbot remains the unchanged placeholder.'

const TABS = [
  'Overview', 'Knowledge Spaces', 'Sources', 'Source Versions', 'Chunking', 'Chunk Quality',
  'Embedding Models', 'Embedding Runs', 'Vector Indexes', 'Keyword Indexes',
  'Retrieval Profiles', 'Retrieval Lab', 'Grounded Generation', 'RAG Chat Lab',
  'Evaluation', 'Index Comparison', 'Manifest',
]

function Pre({ value }) {
  if (!value) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

export default function RagPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', spaces: [], profiles: [], embeddingModels: [], suites: [] })
  const [panelError, setPanelError] = useState('')

  const [spaceForm, setSpaceForm] = useState({ name: '', slug: '' })
  const [selectedSpaceId, setSelectedSpaceId] = useState('')
  const [sources, setSources] = useState({ items: [] })

  const [sourceForm, setSourceForm] = useState({ source_type: 'plain_text', title: '', language: 'ta', licence_status: 'unknown', content: '' })
  const [selectedSourceId, setSelectedSourceId] = useState('')
  const [versions, setVersions] = useState({ items: [] })

  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [chunkSetForm, setChunkSetForm] = useState({ chunking_strategy: 'heading_aware' })
  const [chunkSets, setChunkSets] = useState({ items: [] })
  const [selectedChunkSetId, setSelectedChunkSetId] = useState('')
  const [chunkSetDetail, setChunkSetDetail] = useState(null)
  const [chunks, setChunks] = useState({ items: [] })

  const [embeddingModelForm, setEmbeddingModelForm] = useState({ name: '', version: 'v1', provider_type: 'local_custom_embedding', dimensions: 64, maximum_input_tokens: 256 })
  const [selectedEmbeddingModelId, setSelectedEmbeddingModelId] = useState('')
  const [embeddingRunId, setEmbeddingRunId] = useState('')
  const [embeddingRunDetail, setEmbeddingRunDetail] = useState(null)

  const [vectorIndexId, setVectorIndexId] = useState('')
  const [vectorIndexDetail, setVectorIndexDetail] = useState(null)
  const [keywordIndexId, setKeywordIndexId] = useState('')
  const [keywordIndexDetail, setKeywordIndexDetail] = useState(null)

  const [profileForm, setProfileForm] = useState({ name: '' })
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [defaultProfile, setDefaultProfile] = useState(null)
  const [profileVectorIndexStatus, setProfileVectorIndexStatus] = useState({})
  // MB-48: guards Validate/Activate/Deactivate/Set-as-default against a
  // double-click firing two real mutations for the same profile.
  const [profileActionBusy, setProfileActionBusy] = useState(false)

  const [retrieveQuery, setRetrieveQuery] = useState('')
  const [retrieveResult, setRetrieveResult] = useState(null)

  const [assignmentId, setAssignmentId] = useState('')
  const [groundedQuery, setGroundedQuery] = useState('')
  const [groundedResult, setGroundedResult] = useState(null)

  const [chatSessionId, setChatSessionId] = useState('')
  const [chatMessage, setChatMessage] = useState('')
  const [chatHistory, setChatHistory] = useState([])

  const [suiteForm, setSuiteForm] = useState({ name: '', version: 'v1', evaluation_type: 'retrieval' })
  const [selectedSuiteId, setSelectedSuiteId] = useState('')
  const [fixtureForm, setFixtureForm] = useState({ query: '', language: 'ta', expected_relevant_chunk_ids: '' })
  const [evaluationRunId, setEvaluationRunId] = useState('')
  const [evaluationRunDetail, setEvaluationRunDetail] = useState(null)
  const [evaluationMetrics, setEvaluationMetrics] = useState({ items: [] })

  const [comparisonForm, setComparisonForm] = useState({ left_vector_index_public_id: '', right_vector_index_public_id: '' })
  const [comparisonResult, setComparisonResult] = useState(null)

  const [manifestResult, setManifestResult] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [spaces, profiles, embeddingModels, suites] = await Promise.all([
        ragSpaces(), ragRetrievalProfiles(), ragEmbeddingModels(), ragEvaluationSuites(),
      ])
      setState({
        loading: false, error: '',
        spaces: spaces.items ?? [], profiles: profiles.items ?? [],
        embeddingModels: embeddingModels.items ?? [], suites: suites.items ?? [],
      })
      miniBrainDefaultRetrievalProfile().then(setDefaultProfile).catch(() => setDefaultProfile(null))
      const spaceIds = [...new Set((profiles.items ?? []).map((p) => p.knowledge_space_public_id).filter(Boolean))]
      const entries = await Promise.all(spaceIds.map((id) =>
        ragLatestVectorIndexForSpace(id).then((result) => [id, result]).catch(() => [id, null])
      ))
      setProfileVectorIndexStatus(Object.fromEntries(entries))
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function selectSpace(id) {
    setSelectedSpaceId(id)
    setSources(await ragSources(id).catch(() => ({ items: [] })))
  }

  async function submitSpace(event) {
    event.preventDefault()
    try { await createRagSpace(spaceForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }

  async function submitSource(event) {
    event.preventDefault()
    try {
      await createRagSource(selectedSpaceId, sourceForm)
      setPanelError('')
      await selectSpace(selectedSpaceId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function approveSource(id) {
    try { await patchRagSource(id, { approval_status: 'approved' }); setPanelError(''); await selectSpace(selectedSpaceId) }
    catch (error) { setPanelError(error.message) }
  }

  async function selectSource(id) {
    setSelectedSourceId(id)
    setVersions(await ragSourceVersions(id).catch(() => ({ items: [] })))
  }

  async function createVersion() {
    try { await createRagSourceVersion(selectedSourceId); setPanelError(''); await selectSource(selectedSourceId) }
    catch (error) { setPanelError(error.message) }
  }
  async function verifyVersion(id) {
    try { await validateRagSourceVersion(id); setPanelError(''); await selectSource(selectedSourceId) }
    catch (error) { setPanelError(error.message) }
  }

  async function submitChunkSet(event) {
    event.preventDefault()
    try {
      const created = await createRagChunkSet(selectedVersionId, chunkSetForm)
      setPanelError('')
      setChunkSets(await ragSources(selectedSpaceId).then(() => ({ items: [created] })).catch(() => ({ items: [created] })))
      await selectChunkSet(created.public_id)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function selectChunkSet(id) {
    setSelectedChunkSetId(id)
    setChunkSetDetail(await ragChunkSet(id).catch(() => null))
    setChunks(await ragChunks(id).catch(() => ({ items: [] })))
  }
  async function runValidateChunkSet() {
    try { await validateRagChunkSet(selectedChunkSetId); setPanelError(''); await selectChunkSet(selectedChunkSetId) }
    catch (error) { setPanelError(error.message) }
  }

  async function submitEmbeddingModel(event) {
    event.preventDefault()
    try {
      await createRagEmbeddingModel({
        ...embeddingModelForm,
        dimensions: Number(embeddingModelForm.dimensions),
        maximum_input_tokens: Number(embeddingModelForm.maximum_input_tokens),
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runEmbeddingRun() {
    try {
      const run = await createRagEmbeddingRun(selectedChunkSetId, { embedding_model_public_id: selectedEmbeddingModelId })
      setEmbeddingRunId(run.public_id)
      setEmbeddingRunDetail(run)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runExecuteEmbeddingRun() {
    try { setEmbeddingRunDetail(await executeRagEmbeddingRun(embeddingRunId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function loadEmbeddingRun() {
    setEmbeddingRunDetail(await ragEmbeddingRun(embeddingRunId).catch(() => null))
  }

  async function runCreateVectorIndex() {
    try { const index = await createRagVectorIndex(embeddingRunId); setVectorIndexId(index.public_id); setVectorIndexDetail(index); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runBuildVectorIndex() {
    try { setVectorIndexDetail(await buildRagVectorIndex(vectorIndexId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidateVectorIndex() {
    try { setVectorIndexDetail(await validateRagVectorIndex(vectorIndexId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runActivateVectorIndex() {
    try { setVectorIndexDetail(await activateRagVectorIndex(vectorIndexId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function loadVectorIndex() {
    setVectorIndexDetail(await ragVectorIndex(vectorIndexId).catch(() => null))
  }

  async function runCreateKeywordIndex() {
    try { const index = await createRagKeywordIndex(selectedChunkSetId); setKeywordIndexId(index.public_id); setKeywordIndexDetail(index); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runBuildKeywordIndex() {
    try { setKeywordIndexDetail(await buildRagKeywordIndex(keywordIndexId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidateKeywordIndex() {
    try { setKeywordIndexDetail(await validateRagKeywordIndex(keywordIndexId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runActivateKeywordIndex() {
    try { setKeywordIndexDetail(await activateRagKeywordIndex(keywordIndexId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function loadKeywordIndex() {
    setKeywordIndexDetail(await ragKeywordIndex(keywordIndexId).catch(() => null))
  }

  async function submitProfile(event) {
    event.preventDefault()
    try { await createRagRetrievalProfile(selectedSpaceId, profileForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidateProfile() {
    if (profileActionBusy) return
    setProfileActionBusy(true)
    try { await validateRagRetrievalProfile(selectedProfileId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
    finally { setProfileActionBusy(false) }
  }
  async function runActivateProfile() {
    if (profileActionBusy) return
    setProfileActionBusy(true)
    try { await activateRagRetrievalProfile(selectedProfileId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
    finally { setProfileActionBusy(false) }
  }
  async function runDeactivateProfile(id) {
    if (profileActionBusy) return
    setProfileActionBusy(true)
    try { await deactivateRagRetrievalProfile(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
    finally { setProfileActionBusy(false) }
  }
  async function runSetDefaultProfile(id) {
    if (profileActionBusy) return
    setProfileActionBusy(true)
    try { await miniBrainSetDefaultRetrievalProfile(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
    finally { setProfileActionBusy(false) }
  }

  async function runRetrieve(event) {
    event.preventDefault()
    try {
      setRetrieveResult(await ragRetrieve({ retrieval_profile_public_id: selectedProfileId, query: retrieveQuery }))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGroundedAnswer(event) {
    event.preventDefault()
    try {
      setGroundedResult(await ragGroundedAnswer({
        retrieval_profile_public_id: selectedProfileId,
        assignment_public_id: assignmentId,
        query: groundedQuery,
      }))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function openChatSession() {
    try {
      const session = await createRagChatLabSession({ retrieval_profile_public_id: selectedProfileId, assignment_public_id: assignmentId })
      setChatSessionId(session.session.public_id)
      setChatHistory([])
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function sendChatMessage(event) {
    event.preventDefault()
    try {
      const result = await postRagChatLabMessage(chatSessionId, chatMessage, selectedProfileId)
      setChatHistory((old) => [...old, { role: 'user', text: chatMessage }, { role: 'assistant', text: result.answer_text, status: result.answer?.answer_status }])
      setChatMessage('')
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function closeChat() {
    try { await closeRagChatLabSession(chatSessionId); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  async function submitSuite(event) {
    event.preventDefault()
    try { await createRagEvaluationSuite(selectedSpaceId, suiteForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function submitFixture(event) {
    event.preventDefault()
    try {
      const relevantIds = fixtureForm.expected_relevant_chunk_ids.split(',').map((id) => id.trim()).filter(Boolean)
      await addRagEvaluationFixture(selectedSuiteId, { ...fixtureForm, expected_relevant_chunk_ids: relevantIds })
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runCreateEvaluationRun() {
    try {
      const run = await createRagEvaluationRun(selectedSuiteId, { retrieval_profile_public_id: selectedProfileId })
      setEvaluationRunId(run.public_id)
      setEvaluationRunDetail(run)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runExecuteEvaluationRun() {
    try {
      setEvaluationRunDetail(await executeRagEvaluationRun(evaluationRunId))
      setEvaluationMetrics(await ragEvaluationMetrics(evaluationRunId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitComparison(event) {
    event.preventDefault()
    try { setComparisonResult(await createRagIndexComparison(comparisonForm)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  async function runGenerateManifest() {
    try { setManifestResult(await generateRagManifest(selectedSpaceId)); setManifestVerification(null); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runVerifyManifest() {
    try { setManifestVerification(await verifyRagManifest(selectedSpaceId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  if (state.loading) return <section className="notice">Loading knowledge and RAG workspace…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Knowledge &amp; RAG</h2>
          <p className="notice">{RAG_NOTICE}</p>
          <p className="notice">{NO_PUBLIC_ACTIVATION_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Knowledge and RAG sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Knowledge Spaces</h3>
          {(state.spaces ?? []).length === 0 && <article>No knowledge spaces yet.</article>}
          {(state.spaces ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => selectSpace(item.public_id)}>
              <strong>{item.name}</strong>
              <span>{item.lifecycle_status}</span>
            </button>
          ))}
          <h3>Retrieval Profiles</h3>
          {(state.profiles ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => setSelectedProfileId(item.public_id)}>
              <strong>{item.name}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Knowledge spaces" value={state.spaces.length} tone="neutral" />
                <StatusCard label="Retrieval profiles" value={state.profiles.length} tone="neutral" />
                <StatusCard label="Embedding models" value={state.embeddingModels.length} tone="neutral" />
                <StatusCard label="Evaluation suites" value={state.suites.length} tone="neutral" />
                <StatusCard label="Public chat" value="placeholder" tone="good" />
              </div>
              <p className="notice">{INJECTION_NOTICE}</p>
              <p className="notice">Governed, rights-checked RAG ingestion (selecting only approved, traceable content and never auto-activating an index) is available from the Builds &amp; Pipelines page.</p>
              {selectedSpaceId && <p className="notice">Selected space: {selectedSpaceId.slice(0, 8)}</p>}
              {selectedProfileId && <p className="notice">Selected retrieval profile: {selectedProfileId.slice(0, 8)}</p>}
            </>
          )}

          {tab === 'Knowledge Spaces' && (
            <>
              <form className="inline-form training-form" onSubmit={submitSpace}>
                <h3>Create knowledge space</h3>
                <label>Name<input value={spaceForm.name} onChange={(e) => setSpaceForm({ ...spaceForm, name: e.target.value })} /></label>
                <label>Slug<input value={spaceForm.slug} onChange={(e) => setSpaceForm({ ...spaceForm, slug: e.target.value })} /></label>
                <button type="submit">Create space</button>
              </form>
              {selectedSpaceId && <p className="notice">Selected: {selectedSpaceId.slice(0, 8)}</p>}
            </>
          )}

          {tab === 'Sources' && (
            <>
              {!selectedSpaceId && <p className="notice">Select a knowledge space from the left first.</p>}
              {selectedSpaceId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitSource}>
                    <h3>Register knowledge source</h3>
                    <label>Source type
                      <select value={sourceForm.source_type} onChange={(e) => setSourceForm({ ...sourceForm, source_type: e.target.value })}>
                        <option value="plain_text">plain_text</option>
                        <option value="markdown">markdown</option>
                        <option value="html_snapshot">html_snapshot</option>
                        <option value="manual_admin_content">manual_admin_content</option>
                        <option value="course_material">course_material</option>
                        <option value="faq">faq</option>
                        <option value="dataset_version">dataset_version</option>
                        <option value="pdf_document">pdf_document</option>
                      </select>
                    </label>
                    <label>Title<input value={sourceForm.title} onChange={(e) => setSourceForm({ ...sourceForm, title: e.target.value })} /></label>
                    <label>Language<input value={sourceForm.language} onChange={(e) => setSourceForm({ ...sourceForm, language: e.target.value })} /></label>
                    <label>Content (inline types only)
                      <textarea value={sourceForm.content} onChange={(e) => setSourceForm({ ...sourceForm, content: e.target.value })} rows={4} />
                    </label>
                    <button type="submit">Register source</button>
                  </form>
                  <div className="data-list">
                    {(sources.items ?? []).map((item) => (
                      <article key={item.public_id}>
                        <strong>{item.title}</strong> — {item.source_type}, approval: {item.approval_status}
                        <div className="inline-form">
                          <button onClick={() => selectSource(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                          {item.approval_status !== 'approved' && (
                            <button onClick={() => approveSource(item.public_id)}>Approve</button>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Source Versions' && (
            <>
              {!selectedSourceId && <p className="notice">Select a source from the Sources tab first.</p>}
              {selectedSourceId && (
                <>
                  <button onClick={createVersion}>Create new version from current source content</button>
                  <div className="data-list">
                    {(versions.items ?? []).map((item) => (
                      <article key={item.public_id}>
                        <strong>v{item.version_number}</strong> — {item.status}, checksum {item.content_checksum_sha256?.slice(0, 12)}
                        <div className="inline-form">
                          <button onClick={() => setSelectedVersionId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                          <button onClick={() => verifyVersion(item.public_id)}>Validate</button>
                        </div>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Chunking' && (
            <>
              {!selectedVersionId && <p className="notice">Select a source version from Source Versions first.</p>}
              {selectedVersionId && (
                <form className="inline-form training-form" onSubmit={submitChunkSet}>
                  <h3>Create chunk set</h3>
                  <label>Chunking strategy
                    <select value={chunkSetForm.chunking_strategy} onChange={(e) => setChunkSetForm({ ...chunkSetForm, chunking_strategy: e.target.value })}>
                      <option value="heading_aware">heading_aware</option>
                      <option value="paragraph">paragraph</option>
                      <option value="sentence_window">sentence_window</option>
                      <option value="fixed_token_window">fixed_token_window</option>
                      <option value="record_based">record_based</option>
                    </select>
                  </label>
                  <button type="submit">Chunk this version</button>
                </form>
              )}
              {chunkSetDetail && (
                <div className="metric-grid">
                  <StatusCard label="Total chunks" value={chunkSetDetail.total_chunks} tone="neutral" />
                  <StatusCard label="Accepted" value={chunkSetDetail.accepted_chunks} tone="good" />
                  <StatusCard label="Warning" value={chunkSetDetail.warning_chunks} tone="warning" />
                  <StatusCard label="Rejected" value={chunkSetDetail.rejected_chunks} tone="bad" />
                  <StatusCard label="Quarantined" value={chunkSetDetail.quarantined_chunks} tone="bad" />
                </div>
              )}
              {selectedChunkSetId && <button onClick={runValidateChunkSet}>Validate chunk set</button>}
            </>
          )}

          {tab === 'Chunk Quality' && (
            <>
              <p className="notice">{INJECTION_NOTICE}</p>
              <div className="data-list">
                {(chunks.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>#{item.sequence_number}</strong> — quality: {item.quality_status}, injection: {item.injection_status}
                    <div className="notice">{(item.quality_issues ?? []).join(', ') || 'no issues'}</div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Embedding Models' && (
            <>
              <form className="inline-form training-form" onSubmit={submitEmbeddingModel}>
                <h3>Register embedding model</h3>
                <label>Name<input value={embeddingModelForm.name} onChange={(e) => setEmbeddingModelForm({ ...embeddingModelForm, name: e.target.value })} /></label>
                <label>Provider
                  <select value={embeddingModelForm.provider_type} onChange={(e) => setEmbeddingModelForm({ ...embeddingModelForm, provider_type: e.target.value })}>
                    <option value="local_custom_embedding">local_custom_embedding (bounded hashing-trick)</option>
                    <option value="deterministic_test_embedding">deterministic_test_embedding (tests only)</option>
                    <option value="local_sentence_transformer">local_sentence_transformer (not yet implemented)</option>
                  </select>
                </label>
                <label>Dimensions<input type="number" value={embeddingModelForm.dimensions} onChange={(e) => setEmbeddingModelForm({ ...embeddingModelForm, dimensions: e.target.value })} /></label>
                <button type="submit">Register model</button>
              </form>
              <div className="data-list">
                {(state.embeddingModels ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.provider_type}, dims {item.dimensions}
                    <button onClick={() => setSelectedEmbeddingModelId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Embedding Runs' && (
            <>
              <p className="notice">Requires a selected chunk set (Chunking tab) and embedding model (above).</p>
              <div className="inline-form">
                <button onClick={runEmbeddingRun}>Create embedding run</button>
                <button onClick={runExecuteEmbeddingRun}>Execute run</button>
                <button onClick={loadEmbeddingRun}>Refresh</button>
              </div>
              <Pre value={embeddingRunDetail} />
            </>
          )}

          {tab === 'Vector Indexes' && (
            <>
              <p className="notice">Requires a completed embedding run (above).</p>
              <div className="inline-form">
                <button onClick={runCreateVectorIndex}>Create vector index</button>
                <button onClick={runBuildVectorIndex}>Build</button>
                <button onClick={runValidateVectorIndex}>Validate</button>
                <button onClick={runActivateVectorIndex}>Activate</button>
                <button onClick={loadVectorIndex}>Refresh</button>
              </div>
              <Pre value={vectorIndexDetail} />
            </>
          )}

          {tab === 'Keyword Indexes' && (
            <>
              <p className="notice">FTS5-backed keyword index; does not perform true Tamil morphological segmentation (documented limitation).</p>
              <div className="inline-form">
                <button onClick={runCreateKeywordIndex}>Create keyword index</button>
                <button onClick={runBuildKeywordIndex}>Build</button>
                <button onClick={runValidateKeywordIndex}>Validate</button>
                <button onClick={runActivateKeywordIndex}>Activate</button>
                <button onClick={loadKeywordIndex}>Refresh</button>
              </div>
              <Pre value={keywordIndexDetail} />
            </>
          )}

          {tab === 'Retrieval Profiles' && (
            <>
              {!selectedSpaceId && <p className="notice">Select a knowledge space first.</p>}
              {selectedSpaceId && (
                <form className="inline-form training-form" onSubmit={submitProfile}>
                  <h3>Create retrieval profile</h3>
                  <label>Name<input value={profileForm.name} onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })} /></label>
                  <button type="submit">Create profile</button>
                </form>
              )}
              {selectedProfileId && (
                <div className="inline-form">
                  <span>Selected: {selectedProfileId.slice(0, 8)}</span>
                  <button onClick={runValidateProfile} disabled={profileActionBusy}>{profileActionBusy ? 'Working…' : 'Validate'}</button>
                  <button onClick={runActivateProfile} disabled={profileActionBusy}>{profileActionBusy ? 'Working…' : 'Activate'}</button>
                </div>
              )}

              <h3>Retrieval Profile Management</h3>
              <p className="notice">Only active profiles can be set as the default grounded-chat profile. Deactivating the current default falls back to auto-selection.</p>
              {defaultProfile?.retrieval_profile_public_id && (
                <p className="notice">Current grounded-chat default: {defaultProfile.name ?? defaultProfile.retrieval_profile_public_id.slice(0, 8)}</p>
              )}
              {(state.profiles ?? []).length === 0 && <article>No retrieval profiles yet.</article>}
              {(state.profiles ?? []).length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Knowledge space</th>
                        <th>Vector index</th>
                        <th>Default</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {state.profiles.map((item) => {
                        const vectorIndex = profileVectorIndexStatus[item.knowledge_space_public_id]
                        const isDefault = defaultProfile?.retrieval_profile_public_id === item.public_id
                        return (
                          <tr key={item.public_id}>
                            <td>{item.name}</td>
                            <td>{item.status}</td>
                            <td>{item.knowledge_space_name ?? '--'}</td>
                            <td>{vectorIndex ? vectorIndex.status : 'none built'}</td>
                            <td>{isDefault ? 'default' : ''}</td>
                            <td>
                              <div className="inline-form">
                                {item.status === 'active' && (
                                  <button onClick={() => runDeactivateProfile(item.public_id)} disabled={profileActionBusy}>Deactivate</button>
                                )}
                                {item.status === 'active' && !isDefault && (
                                  <button onClick={() => runSetDefaultProfile(item.public_id)} disabled={profileActionBusy}>Set as default</button>
                                )}
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {tab === 'Retrieval Lab' && (
            <>
              <p className="notice">{INJECTION_NOTICE}</p>
              <form className="inline-form training-form" onSubmit={runRetrieve}>
                <label>Query<input value={retrieveQuery} onChange={(e) => setRetrieveQuery(e.target.value)} /></label>
                <button type="submit">Retrieve (uses selected profile)</button>
              </form>
              <Pre value={retrieveResult} />
            </>
          )}

          {tab === 'Grounded Generation' && (
            <>
              <p className="notice">{DIAGNOSTIC_DISCLAIMER}</p>
              <form className="inline-form training-form" onSubmit={runGroundedAnswer}>
                <label>Admin inference assignment public ID<input value={assignmentId} onChange={(e) => setAssignmentId(e.target.value)} /></label>
                <label>Query<input value={groundedQuery} onChange={(e) => setGroundedQuery(e.target.value)} /></label>
                <button type="submit">Generate grounded answer (uses selected profile)</button>
              </form>
              <Pre value={groundedResult} />
            </>
          )}

          {tab === 'RAG Chat Lab' && (
            <>
              <p className="notice">{DIAGNOSTIC_DISCLAIMER} Every turn re-runs retrieval from scratch -- there is no session-level memory of prior evidence.</p>
              <label>Admin inference assignment public ID<input value={assignmentId} onChange={(e) => setAssignmentId(e.target.value)} /></label>
              <div className="inline-form">
                <button onClick={openChatSession}>Open chat-lab session</button>
                <button onClick={closeChat}>Close session</button>
              </div>
              {chatSessionId && (
                <>
                  <div className="data-list">
                    {chatHistory.map((turn, index) => (
                      <article key={index}><strong>{turn.role}:</strong> {turn.text} {turn.status && <em>({turn.status})</em>}</article>
                    ))}
                  </div>
                  <form className="inline-form training-form" onSubmit={sendChatMessage}>
                    <label>Message<input value={chatMessage} onChange={(e) => setChatMessage(e.target.value)} /></label>
                    <button type="submit">Send</button>
                  </form>
                </>
              )}
            </>
          )}

          {tab === 'Evaluation' && (
            <>
              {!selectedSpaceId && <p className="notice">Select a knowledge space first.</p>}
              {selectedSpaceId && (
                <form className="inline-form training-form" onSubmit={submitSuite}>
                  <h3>Create evaluation suite</h3>
                  <label>Name<input value={suiteForm.name} onChange={(e) => setSuiteForm({ ...suiteForm, name: e.target.value })} /></label>
                  <label>Type
                    <select value={suiteForm.evaluation_type} onChange={(e) => setSuiteForm({ ...suiteForm, evaluation_type: e.target.value })}>
                      <option value="retrieval">retrieval</option>
                      <option value="generation">generation</option>
                      <option value="both">both</option>
                    </select>
                  </label>
                  <button type="submit">Create suite</button>
                </form>
              )}
              <div className="data-list">
                {(state.suites ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.evaluation_type}
                    <button onClick={() => setSelectedSuiteId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                  </article>
                ))}
              </div>
              {selectedSuiteId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitFixture}>
                    <h4>Add fixture (known relevant chunk IDs only -- never fabricated)</h4>
                    <label>Query<input value={fixtureForm.query} onChange={(e) => setFixtureForm({ ...fixtureForm, query: e.target.value })} /></label>
                    <label>Expected relevant chunk IDs (comma separated)
                      <input value={fixtureForm.expected_relevant_chunk_ids} onChange={(e) => setFixtureForm({ ...fixtureForm, expected_relevant_chunk_ids: e.target.value })} />
                    </label>
                    <button type="submit">Add fixture</button>
                  </form>
                  <div className="inline-form">
                    <button onClick={runCreateEvaluationRun}>Create evaluation run (uses selected profile)</button>
                    <button onClick={runExecuteEvaluationRun}>Execute run</button>
                  </div>
                  <Pre value={evaluationRunDetail} />
                  {(evaluationMetrics.items ?? []).map((item) => (
                    <article key={item.public_id}>{item.metric_scope}/{item.metric_name}: {item.metric_value}</article>
                  ))}
                </>
              )}
            </>
          )}

          {tab === 'Index Comparison' && (
            <>
              <form className="inline-form training-form" onSubmit={submitComparison}>
                <h3>Compare two vector indexes</h3>
                <label>Left vector index public ID<input value={comparisonForm.left_vector_index_public_id} onChange={(e) => setComparisonForm({ ...comparisonForm, left_vector_index_public_id: e.target.value })} /></label>
                <label>Right vector index public ID<input value={comparisonForm.right_vector_index_public_id} onChange={(e) => setComparisonForm({ ...comparisonForm, right_vector_index_public_id: e.target.value })} /></label>
                <button type="submit">Compare</button>
              </form>
              <Pre value={comparisonResult} />
            </>
          )}

          {tab === 'Manifest' && (
            <>
              <p className="notice">The RAG manifest never includes raw content, absolute paths, or secrets -- checksums and configuration only.</p>
              <div className="inline-form">
                <button onClick={runGenerateManifest}>Generate/view manifest</button>
                <button onClick={runVerifyManifest}>Verify checksum</button>
              </div>
              <Pre value={manifestResult} />
              <Pre value={manifestVerification} />
            </>
          )}
        </section>
      </div>
    </section>
  )
}
