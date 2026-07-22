import { useEffect, useRef, useState } from 'react'
import { createDatasetRecord, createDatasetSource, datasetDuplicates, datasetRecords, datasetSources, datasetStatistics, recordAction, recordReviews, updateDatasetRecord, updateDatasetSource } from '../services/api.js'

const tabs = ['Overview', 'Sources', 'Records', 'Review Queue', 'Duplicates']
const emptyRecord = { source_public_id: '', record_type: 'instruction', language: 'ta', instruction: '', input_text: '', output_text: '', normalized_input: '', metadata: {} }

export default function DatasetsPage() {
  const [tab, setTab] = useState('Overview'), [data, setData] = useState(null), [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [sourceForm, setSourceForm] = useState({ name: '', language: 'ta', licence_status: 'unknown', source_type: 'manual', metadata: {} })
  const [recordForm, setRecordForm] = useState(emptyRecord), [comments, setComments] = useState({})
  const [editingSource, setEditingSource] = useState(null), [editingRecord, setEditingRecord] = useState(null)
  const requestSequence = useRef(0)
  const activeTab = useRef(tab)
  async function load(active = tab) {
    const sequence = ++requestSequence.current
    setLoading(true); setError('')
    try {
      const sourcePage = await datasetSources()
      let nextData
      if (active === 'Overview') nextData = await datasetStatistics()
      else if (active === 'Sources') nextData = sourcePage
      else if (active === 'Records') nextData = await datasetRecords()
      else if (active === 'Review Queue') nextData = await datasetRecords('?status=pending_review')
      else nextData = await datasetDuplicates()
      if (sequence === requestSequence.current) { setSources(sourcePage.items); setData(nextData) }
    } catch (reason) { if (sequence === requestSequence.current) setError(reason.message) } finally { if (sequence === requestSequence.current) setLoading(false) }
  }
  useEffect(() => { activeTab.current = tab; load(tab) }, [tab])
  async function saveSource(e) { e.preventDefault(); try { editingSource ? await updateDatasetSource(editingSource, sourceForm) : await createDatasetSource(sourceForm); setNotice(editingSource ? 'Source updated.' : 'Manual source created.'); setEditingSource(null); setSourceForm({ name: '', language: 'ta', licence_status: 'unknown', source_type: 'manual', metadata: {} }); load('Sources') } catch (reason) { setError(reason.message) } }
  async function saveRecord(e) { e.preventDefault(); try { editingRecord ? await updateDatasetRecord(editingRecord, recordForm) : await createDatasetRecord(recordForm); setNotice(editingRecord ? 'Record updated.' : 'Draft record created.'); setEditingRecord(null); setRecordForm(emptyRecord); load('Records') } catch (reason) { setError(reason.message) } }
  function editSource(source) { setEditingSource(source.public_id); setSourceForm({ name: source.name, language: source.language, licence_status: source.licence_status, source_type: source.source_type, metadata: source.metadata || {} }) }
  function editRecord(record) { setEditingRecord(record.public_id); setRecordForm({ source_public_id: record.source_public_id, record_type: record.record_type, language: record.language, instruction: record.instruction || '', input_text: record.input_text || '', output_text: record.output_text || '', normalized_input: record.normalized_input || '', metadata: record.metadata || {} }) }
  async function act(record, action, decision) { try { await recordAction(record.public_id, action, decision ? { decision, comments: comments[record.public_id] || null } : null); setNotice('Record updated.'); load(activeTab.current) } catch (reason) { setError(reason.message) } }
  async function history(record) { const result = await recordReviews(record.public_id); setNotice(`${result.items.length} review event(s) recorded.`) }
  return <><div className="dataset-tabs">{tabs.map((item) => <button className={tab === item ? 'active' : ''} onClick={() => { activeTab.current = item; setData(null); setTab(item) }} key={item}>{item}</button>)}</div>
    {notice && <div className="success-note" role="status">{notice}</div>}{error && <div className="form-error" role="alert">{error}</div>}
    {loading || !data ? <div className="notice">Loading dataset workspace…</div> : <DatasetContent tab={tab} data={data} sources={sources} sourceForm={sourceForm} setSourceForm={setSourceForm} recordForm={recordForm} setRecordForm={setRecordForm} saveSource={saveSource} saveRecord={saveRecord} act={act} comments={comments} setComments={setComments} history={history} editingSource={editingSource} editingRecord={editingRecord} editSource={editSource} editRecord={editRecord} />}
  </>
}

function DatasetContent({ tab, data, sources, sourceForm, setSourceForm, recordForm, setRecordForm, saveSource, saveRecord, act, comments, setComments, history, editingSource, editingRecord, editSource, editRecord }) {
  if (tab === 'Overview') return <><h2>Dataset overview</h2><section className="metric-grid">{Object.entries(data).filter(([,v]) => typeof v !== 'object').map(([k,v]) => <article className="status-card" key={k}><span>{k.replaceAll('_',' ')}</span><strong>{v}</strong></article>)}</section><Distribution title="Status" data={data.by_status}/><Distribution title="Languages" data={data.by_language}/><Distribution title="Record types" data={data.by_record_type}/></>
  if (tab === 'Sources') return <><form className="inline-form" onSubmit={saveSource}><h2>{editingSource ? 'Edit source' : 'Create manual source'}</h2><label>Name<input value={sourceForm.name} onChange={(e)=>setSourceForm({...sourceForm,name:e.target.value})} required /></label><label>Language<select value={sourceForm.language} onChange={(e)=>setSourceForm({...sourceForm,language:e.target.value})}><option value="ta">Tamil</option><option value="en">English</option><option value="tgl">Tanglish</option><option value="mixed">Mixed</option></select></label><button>{editingSource ? 'Save source' : 'Create source'}</button></form><ItemList items={data.items} empty="No dataset sources yet." onEdit={editSource} /></>
  if (tab === 'Records') return <><form className="inline-form record-form" onSubmit={saveRecord}><h2>{editingRecord ? 'Edit dataset record' : 'Create dataset record'}</h2><label>Source<select value={recordForm.source_public_id} onChange={(e)=>setRecordForm({...recordForm,source_public_id:e.target.value})} required><option value="">Select source</option>{sources.map(s=><option key={s.public_id} value={s.public_id}>{s.name}</option>)}</select></label><label>Type<select value={recordForm.record_type} onChange={(e)=>setRecordForm({...recordForm,record_type:e.target.value})}>{['pretrain','instruction','chat','translation','tanglish_pair','safety','preference'].map(x=><option key={x}>{x}</option>)}</select></label><label>Language<select value={recordForm.language} onChange={(e)=>setRecordForm({...recordForm,language:e.target.value})}>{['ta','en','tgl','mixed'].map(x=><option key={x}>{x}</option>)}</select></label><label>Instruction<textarea value={recordForm.instruction} onChange={(e)=>setRecordForm({...recordForm,instruction:e.target.value})}/></label><label>Input<textarea value={recordForm.input_text} onChange={(e)=>setRecordForm({...recordForm,input_text:e.target.value})}/></label><label>Output<textarea value={recordForm.output_text} onChange={(e)=>setRecordForm({...recordForm,output_text:e.target.value})}/></label><button>{editingRecord ? 'Save record' : 'Create draft'}</button></form><RecordList items={data.items} act={act} history={history} editRecord={editRecord} /></>
  if (tab === 'Review Queue') return <><h2>Review queue</h2>{!data.items.length ? <div className="notice">No records are waiting for review.</div> : data.items.map(r=><article className="review-card" key={r.public_id}><strong>{r.instruction || r.record_type}</strong><p>{r.input_text}</p><p>{r.output_text}</p><label>Review comments<textarea value={comments[r.public_id]||''} onChange={e=>setComments({...comments,[r.public_id]:e.target.value})}/></label><div><button onClick={()=>act(r,'review','approve')}>Approve</button><button onClick={()=>act(r,'review','reject')}>Reject</button><button onClick={()=>act(r,'review','request_changes')}>Request changes</button><button onClick={()=>history(r)}>History</button></div></article>)}</>
  return <><h2>Duplicate conflicts</h2><ItemList items={data.items} empty="No duplicate conflicts recorded." /></>
}
function Distribution({ title, data }) { return <><h3>{title}</h3><div className="distribution">{Object.entries(data).map(([k,v])=><span key={k}>{k}: <strong>{v}</strong></span>)}</div></> }
function ItemList({ items = [], empty, onEdit }) { return !items.length ? <div className="notice">{empty}</div> : <div className="data-list">{items.map((item)=><article key={item.public_id || item.created_at}><strong>{item.name || item.existing_record_public_id}</strong><span>{item.status || item.created_at}</span>{onEdit && <button onClick={()=>onEdit(item)}>Edit</button>}</article>)}</div> }
function RecordList({ items = [], act, history, editRecord }) { return !items.length ? <div className="notice">No records yet.</div> : <div className="data-list">{items.map(r=><article key={r.public_id}><div><strong>{r.instruction || r.record_type}</strong><small>{r.language} · {r.status}</small></div><div>{['draft','pending_review'].includes(r.status)&&<button onClick={()=>editRecord(r)}>Edit</button>}{r.status==='draft'&&<button onClick={()=>act(r,'submit')}>Submit</button>}{r.status!=='archived'&&<button onClick={()=>act(r,'archive')}>Archive</button>}{r.status==='archived'&&<button onClick={()=>act(r,'restore')}>Restore</button>}<button onClick={()=>history(r)}>History</button></div></article>)}</div> }
