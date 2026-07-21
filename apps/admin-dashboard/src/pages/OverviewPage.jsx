import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import { getOverview } from '../services/api.js'

export default function OverviewPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { getOverview().then(setData).catch((reason) => setError(reason.message)) }, [])
  if (error) return <div className="notice error-notice"><strong>Unable to load overview</strong><p>{error}</p></div>
  if (!data) return <div className="notice">Loading system overview…</div>
  return <>
    <section className="intro"><div><span>System snapshot</span><h2>{data.project} is ready for foundation work.</h2></div><div className="phase-number">01</div></section>
    <h3>Product status</h3><section className="card-grid">
      <StatusCard label="Chatbot" value={data.chatbot_status} tone="good" />
      <StatusCard label="Admin dashboard" value={data.admin_dashboard_status} tone="good" />
      <StatusCard label="Core model" value={data.core_model_status} tone="waiting" />
    </section>
    <h3>Foundation records</h3><section className="metric-grid">
      <StatusCard label="Dataset records" value={data.dataset_records} />
      <StatusCard label="Training jobs" value={data.training_jobs} />
      <StatusCard label="Registered models" value={data.registered_models} />
    </section>
  </>
}
