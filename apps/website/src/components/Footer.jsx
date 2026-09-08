import { Link } from 'react-router-dom'

const PRODUCT_LINKS = [
  { label: 'Chat',         to: '/chat' },
  { label: 'Features',     to: '/features' },
  { label: 'How It Works', to: '/how-it-works' },
  { label: 'Desktop App',  to: '/desktop' },
]

const SUPPORT_LINKS = [
  { label: 'Help / Getting Started', to: '/help' },
  { label: 'FAQ',                    to: '/faq' },
]

const LEGAL_LINKS = [
  { label: 'Privacy',      to: '/privacy' },
  { label: 'Terms of Use', to: '/terms' },
]

export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="footer" role="contentinfo">
      <div className="container">
        <div className="footer-inner">
          {/* Brand */}
          <div className="footer-brand">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
              <div className="navbar-logo-mark" aria-hidden="true">B</div>
              <span style={{ fontWeight: 800, fontSize: 'var(--font-size-base)' }}>Brud AI</span>
            </div>
            <p>Multilingual AI chat with Tamil and English support. Evidence-grounded, privacy-first.</p>
          </div>

          {/* Product */}
          <div>
            <p className="footer-col-title">Product</p>
            <ul className="footer-links" role="list">
              {PRODUCT_LINKS.map((l) => (
                <li key={l.to}><Link to={l.to}>{l.label}</Link></li>
              ))}
            </ul>
          </div>

          {/* Support */}
          <div>
            <p className="footer-col-title">Support</p>
            <ul className="footer-links" role="list">
              {SUPPORT_LINKS.map((l) => (
                <li key={l.to}><Link to={l.to}>{l.label}</Link></li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <p className="footer-col-title">Legal</p>
            <ul className="footer-links" role="list">
              {LEGAL_LINKS.map((l) => (
                <li key={l.to}><Link to={l.to}>{l.label}</Link></li>
              ))}
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>© {year} Brud AI. All rights reserved.</p>
          <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            AI responses may be imperfect. Do not rely on them for critical decisions.
          </p>
        </div>
      </div>
    </footer>
  )
}
