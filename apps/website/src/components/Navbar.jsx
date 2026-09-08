import { useState } from 'react'
import { NavLink, Link } from 'react-router-dom'

const NAV_ITEMS = [
  { label: 'Home',         to: '/' },
  { label: 'Chat',         to: '/chat' },
  { label: 'Features',     to: '/features' },
  { label: 'How It Works', to: '/how-it-works' },
  { label: 'FAQ',          to: '/faq' },
  { label: 'Desktop',      to: '/desktop' },
  { label: 'Help',         to: '/help' },
]

// SECURITY NOTE:
// This public navigation intentionally does NOT include any admin, login,
// or dashboard links. Admin access is only through the admin-dashboard app
// at its own dedicated origin. The backend enforces all admin authorization.

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  function closeMobile() { setMobileOpen(false) }

  return (
    <nav className="navbar" role="navigation" aria-label="Main navigation">
      <div className="container navbar-inner">
        <Link to="/" className="navbar-brand" aria-label="Brud AI — Home" onClick={closeMobile}>
          <div className="navbar-logo-mark" aria-hidden="true">B</div>
          <span className="navbar-brand-text">Brud AI</span>
        </Link>

        {/* Desktop nav */}
        <ul className="navbar-nav" role="list">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `navbar-link${isActive ? ' active' : ''}`}
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="navbar-cta" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <Link to="/chat" className="btn btn-primary btn-sm" style={{ display: 'none' }} aria-hidden="true">
            Start Chat
          </Link>
          {/* Mobile toggle */}
          <button
            className="navbar-toggle"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            aria-controls="mobile-menu"
            onClick={() => setMobileOpen((o) => !o)}
          >
            {mobileOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {/* Mobile panel */}
      {mobileOpen && (
        <div id="mobile-menu" className="navbar-mobile-panel" role="dialog" aria-label="Mobile navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `navbar-link${isActive ? ' active' : ''}`}
              onClick={closeMobile}
            >
              {item.label}
            </NavLink>
          ))}
          <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 'var(--space-4)', marginTop: 'var(--space-2)' }}>
            <Link to="/chat" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={closeMobile}>
              Start Chat
            </Link>
          </div>
        </div>
      )}
    </nav>
  )
}
