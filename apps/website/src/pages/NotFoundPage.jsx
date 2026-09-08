import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - var(--nav-height) - 200px)',
      textAlign: 'center',
      padding: 'var(--space-12) var(--space-4)',
    }}>
      <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }} aria-hidden="true">404</div>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', marginBottom: 'var(--space-4)' }}>Page not found</h1>
      <p style={{ color: 'var(--color-text-secondary)', maxWidth: 400, marginBottom: 'var(--space-8)' }}>
        The page you are looking for does not exist or has been moved.
      </p>
      <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', justifyContent: 'center' }}>
        <Link to="/" className="btn btn-primary">Go Home</Link>
        <Link to="/chat" className="btn btn-secondary">Open Chat</Link>
      </div>
    </div>
  )
}
