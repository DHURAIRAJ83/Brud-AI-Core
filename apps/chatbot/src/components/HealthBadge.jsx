export default function HealthBadge({ status }) {
  const label = status === 'healthy' ? 'Backend online' : status === 'checking' ? 'Checking…' : 'Backend offline'
  return <span className={`health-badge health-${status}`}><span aria-hidden="true" />{label}</span>
}
