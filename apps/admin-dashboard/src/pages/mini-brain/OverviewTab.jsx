import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

function healthTone(status) {
  if (status === 'healthy') return 'good'
  if (status === 'disabled') return 'neutral'
  return 'waiting'
}

export default function OverviewTab({ status, version, busy, toggle, runHealthCheck }) {
  return (
    <>
      {status && version ? (
        <section className="metric-grid">
          <StatusCard label="Enabled" value={String(status.enabled === 1 || status.enabled === true)} tone={status?.enabled ? 'good' : 'neutral'} />
          <StatusCard label="Runtime status" value={status.runtime_status} tone={status?.runtime_status === 'running' ? 'good' : 'neutral'} />
          <StatusCard label="Health" value={status.health?.status} tone={healthTone(status?.health?.status)} />
          <StatusCard label="Version" value={version.module_version} tone="neutral" />
          <StatusCard label="Phase" value={version.phase} tone="neutral" />
          <StatusCard label="Model" value="not integrated" tone="neutral" />
          <StatusCard label="Memory" value="not implemented" tone="neutral" />
        </section>
      ) : (
        <Skeleton lines={3} />
      )}
      <div className="form-row">
        <Button onClick={toggle} disabled={busy}>{status?.enabled ? 'Disable Brud Mini Brain' : 'Enable Brud Mini Brain'}</Button>
        <Button onClick={runHealthCheck}>Run health check</Button>
      </div>
      <div className="notice">
        Brud Mini Brain never modifies existing data directly, never executes training or
        deployment, never replaces the Admin Assistant, and never answers Public Chat.
        Everything here is Admin-only.
      </div>
    </>
  )
}
