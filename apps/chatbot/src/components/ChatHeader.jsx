import HealthBadge from './HealthBadge.jsx'

export default function ChatHeader({ health }) {
  return (
    <header className="chat-header">
      <div><div className="brand">BRUD AI</div><h1>Brud Chat</h1></div>
      <HealthBadge status={health} />
    </header>
  )
}
