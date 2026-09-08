import { Link } from 'react-router-dom'

// IMPORTANT: No desktop binary has been verified in the repository.
// Download links are intentionally disabled. Do NOT add a fake URL.
// Update this page only when an actual verified build is available.

const PLATFORMS = [
  { name: 'macOS', icon: '🍎', status: 'planned' },
  { name: 'Windows', icon: '🪟', status: 'planned' },
  { name: 'Linux', icon: '🐧', status: 'planned' },
]

export default function DesktopPage() {
  return (
    <>
      <div style={{ padding: 'var(--space-16) 0 var(--space-10)', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="container">
          <span className="badge badge-warning" style={{ marginBottom: 'var(--space-4)', display: 'inline-flex' }}>Coming Soon</span>
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>Brud AI Desktop App</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            A native desktop application is planned. It will bring Brud AI to your computer
            with local control and offline capabilities.
          </p>
        </div>
      </div>

      <section className="section-sm">
        <div className="container" style={{ maxWidth: 860, marginInline: 'auto' }}>

          {/* Overview */}
          <div className="card" style={{ marginBottom: 'var(--space-8)' }}>
            <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-4)' }}>Overview</h2>
            <p style={{ color: 'var(--color-text-secondary)', lineHeight: 1.75 }}>
              The Brud AI Desktop App is a planned native application that will allow you to
              interact with Brud AI directly on your computer. It is designed to provide a
              local-first experience where your data stays on your machine.
            </p>
            <div className="notice notice-info" style={{ marginTop: 'var(--space-4)' }}>
              The desktop application has not yet been released. This page describes planned
              functionality. Features and availability are subject to change.
            </div>
          </div>

          {/* Planned features */}
          <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-6)' }}>Planned Features</h2>
          <div className="grid-2" style={{ marginBottom: 'var(--space-8)' }}>
            {[
              { icon: '💻', title: 'Native Application', desc: 'Runs natively on your operating system without a browser.' },
              { icon: '🔒', title: 'Local-First', desc: 'Data remains on your device. Designed for privacy-conscious users.' },
              { icon: '📡', title: 'Offline Capability', desc: 'Planned support for limited offline operation.' },
              { icon: '⚡', title: 'Fast Response', desc: 'Direct connection to backend without browser overhead.' },
            ].map((f) => (
              <div className="card" key={f.title}>
                <div className="feature-icon" aria-hidden="true">{f.icon}</div>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-desc" style={{ margin: 0 }}>{f.desc}</p>
                <span className="badge badge-warning" style={{ marginTop: 'var(--space-3)', display: 'inline-flex' }}>Planned</span>
              </div>
            ))}
          </div>

          {/* Platform support */}
          <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-6)' }}>Platform Support</h2>
          <div className="grid-3" style={{ marginBottom: 'var(--space-8)' }}>
            {PLATFORMS.map((p) => (
              <div className="card" key={p.name} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: 'var(--space-3)' }} aria-hidden="true">{p.icon}</div>
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>{p.name}</h3>
                <span className="badge badge-warning">Planned</span>
              </div>
            ))}
          </div>

          {/* System requirements */}
          <div className="card" style={{ marginBottom: 'var(--space-8)' }}>
            <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-4)' }}>System Requirements</h2>
            <div className="notice notice-info">
              System requirements will be published when the desktop application is ready for release.
              No minimum specifications can be confirmed at this stage.
            </div>
          </div>

          {/* Download section */}
          <div className="card" style={{ marginBottom: 'var(--space-8)', background: 'rgba(103,101,232,0.04)', borderColor: 'rgba(103,101,232,0.2)' }}>
            <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-4)' }}>Download</h2>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-6)' }}>
              No download is currently available. The desktop application has not been released.
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
              {PLATFORMS.map((p) => (
                <button
                  key={p.name}
                  disabled
                  className="btn btn-secondary"
                  aria-label={`Download for ${p.name} — not yet available`}
                  title="Not yet available"
                >
                  {p.icon} {p.name} — Coming Soon
                </button>
              ))}
            </div>
          </div>

          {/* Version / Release Notes */}
          <div className="card" style={{ marginBottom: 'var(--space-8)' }}>
            <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-4)' }}>Version &amp; Release Notes</h2>
            <div className="notice notice-info">
              No release has been published yet. Release notes will appear here when the
              first desktop build is verified and made available.
            </div>
          </div>

          {/* In the meantime */}
          <div className="cta-section">
            <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-4)' }}>In the Meantime</h2>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-6)' }}>
              Use the web-based Brud AI chat while the desktop application is in development.
            </p>
            <Link to="/chat" className="btn btn-primary btn-lg">Open Web Chat</Link>
          </div>
        </div>
      </section>
    </>
  )
}
