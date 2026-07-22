import { useEffect, useState } from 'react'
import {
  coreModelAssignments,
  coreModelCapabilities,
  coreModelCheckpoints,
  coreModelChecks,
  coreModelConfigs,
  coreModelFamilies,
  coreModelVersions,
} from '../services/api.js'

const tabs = ['Overview', 'Families', 'Configurations', 'Versions', 'Architecture Checks', 'Smoke Test', 'Checkpoints', 'Assignments']

export default function CoreModelPage() {
  const [active, setActive] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: null, data: {} })
  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        const [capabilities, families, configs, versions, assignments] = await Promise.all([
          coreModelCapabilities(),
          coreModelFamilies(),
          coreModelConfigs(),
          coreModelVersions(),
          coreModelAssignments(),
        ])
        let checks = { items: [] }
        let checkpoints = { items: [] }
        const first = versions.items?.[0]
        if (first) {
          checks = await coreModelChecks(first.public_id)
          checkpoints = await coreModelCheckpoints(first.public_id)
        }
        if (mounted) setState({ loading: false, error: null, data: { capabilities, families, configs, versions, assignments, checks, checkpoints } })
      } catch (error) {
        if (mounted) setState({ loading: false, error: error.message, data: {} })
      }
    }
    load()
    return () => { mounted = false }
  }, [])
  if (state.loading) return <section className="panel"><p>Loading Core Model foundation…</p></section>
  if (state.error) return <section className="panel error"><p>{state.error}</p></section>
  const { capabilities, families, configs, versions, assignments, checks, checkpoints } = state.data
  const initialized = versions.items?.filter((item) => ['initialized', 'architecture_verified', 'smoke_tested', 'staging', 'active'].includes(item.lifecycle_status)).length ?? 0
  return (
    <section className="stack">
      <div className="page-title"><div><p className="eyebrow">Architecture foundation</p><h1>Core Model</h1><p>CPU-first decoder-only Transformer setup. Random weights are not language-capable.</p></div></div>
      <div className="tabs">{tabs.map((tab) => <button key={tab} className={active === tab ? 'active' : ''} onClick={() => setActive(tab)}>{tab}</button>)}</div>
      {active === 'Overview' && <div className="grid cards">
        <Card title="PyTorch" value={capabilities.pytorch_available ? capabilities.pytorch_version : 'Unavailable'} note={`CUDA: ${capabilities.cuda_available ? 'available' : 'not required'}`} />
        <Card title="Families" value={families.total ?? 0} note="Logical model lines" />
        <Card title="Configs" value={configs.total ?? 0} note="Validated before allocation" />
        <Card title="Initialized" value={initialized} note="Untrained architecture versions" />
      </div>}
      {active === 'Families' && <List title="Families" items={families.items} fields={['name', 'display_name', 'status']} empty="No core model families yet." />}
      {active === 'Configurations' && <List title="Configurations" items={configs.items} fields={['name', 'config_version', 'status', 'parameter_count_estimate', 'memory_estimate_bytes']} empty="Create a Micro or Tiny config through the API or future wizard." />}
      {active === 'Versions' && <List title="Versions" items={versions.items} fields={['version', 'lifecycle_status', 'estimated_parameter_count', 'actual_parameter_count']} empty="No model versions yet." />}
      {active === 'Architecture Checks' && <List title="Latest checks" items={checks.items} fields={['check_name', 'status', 'metric_value', 'created_at']} empty="Run architecture verification to populate checks." />}
      {active === 'Smoke Test' && <section className="panel"><h2>Smoke Test</h2><p>This verifies trainability only. It does not prove language understanding.</p><List items={checks.items?.filter((item) => item.check_name === 'tiny_overfit')} fields={['check_name', 'status', 'metric_value']} empty="No smoke test result yet." /></section>}
      {active === 'Checkpoints' && <List title="Checkpoints" items={checkpoints.items} fields={['checkpoint_type', 'status', 'step', 'file_size_bytes', 'checksum_sha256']} empty="No checkpoints yet." />}
      {active === 'Assignments' && <List title="Assignments" items={assignments.items} fields={['assignment_key', 'enabled', 'updated_at']} empty="No assignments configured." />}
    </section>
  )
}

function Card({ title, value, note }) {
  return <article className="card"><span>{title}</span><strong>{value}</strong><small>{note}</small></article>
}

function List({ title, items = [], fields, empty }) {
  return (
    <section className="panel">
      {title && <h2>{title}</h2>}
      {!items?.length ? <p className="empty">{empty}</p> : <div className="table-wrap"><table><thead><tr>{fields.map((field) => <th key={field}>{field}</th>)}</tr></thead><tbody>{items.map((item) => <tr key={item.public_id ?? item.assignment_key}>{fields.map((field) => <td key={field}>{String(item[field] ?? '—').slice(0, 80)}</td>)}</tr>)}</tbody></table></div>}
    </section>
  )
}
