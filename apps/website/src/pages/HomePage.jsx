import { Link } from 'react-router-dom'
import { useEffect, useRef } from 'react'

const FEATURES = [
  {
    icon: '💬',
    title: 'AI Chat',
    desc: 'Have a natural conversation with Brud AI. Ask questions, explore topics, and get grounded responses.',
  },
  {
    icon: 'அ',
    title: 'Tamil & English',
    desc: 'Chat in Tamil, English, or Tanglish. Tanglish input is automatically responded to in Tamil.',
  },
  {
    icon: '📚',
    title: 'Knowledge Retrieval (RAG)',
    desc: 'Responses are grounded in curated knowledge sources. Brud AI retrieves relevant information before answering.',
  },
  {
    icon: '🧠',
    title: 'Conversation Context',
    desc: 'Brud AI maintains context within a session. Opt-in memory lets you continue where you left off.',
  },
  {
    icon: '🛡️',
    title: 'Safety & Governance',
    desc: 'Built-in content safety evaluation, audit logging, and responsible AI governance at every response.',
  },
  {
    icon: '⚙️',
    title: 'Reliability',
    desc: 'Health monitoring, rate limiting, and operational status ensure a stable service experience.',
  },
]

const FLOW_STEPS = [
  { label: 'You', highlighted: false },
  { label: 'Public Chat', highlighted: true },
  { label: 'Brud AI Core', highlighted: true },
  { label: 'Model + RAG / Tools', highlighted: false },
  { label: 'Grounded Response', highlighted: true },
  { label: 'You', highlighted: false },
]

const FAQS = [
  {
    q: 'What is Brud AI?',
    a: 'Brud AI is a multilingual AI chat assistant supporting Tamil and English. It uses retrieval-augmented generation (RAG) to provide evidence-grounded answers.',
  },
  {
    q: 'Do I need an account to chat?',
    a: 'No account is required for public chat in the current version. Anonymous session support is available. Account-based features are planned for a future release.',
  },
  {
    q: 'Which languages are supported?',
    a: 'Tamil, English, and Tanglish (Tamil written in English characters) are supported. Tanglish input is always responded to in Tamil.',
  },
  {
    q: 'Is there a desktop app?',
    a: 'A desktop application is planned. It is not yet available for download.',
  },
]

export default function HomePage() {
  const featuresRef = useRef(null)

  // Simple intersection observer for fade-in
  useEffect(() => {
    const cards = featuresRef.current?.querySelectorAll('.card') ?? []
    if (!window.IntersectionObserver) return
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.style.opacity = '1'; e.target.style.transform = 'translateY(0)' } }),
      { threshold: 0.1 },
    )
    cards.forEach((c) => { c.style.opacity = '0'; c.style.transform = 'translateY(20px)'; c.style.transition = 'opacity 0.5s ease, transform 0.5s ease'; observer.observe(c) })
    return () => observer.disconnect()
  }, [])

  return (
    <>
      {/* ── Hero ── */}
      <section className="hero" aria-label="Brud AI introduction">
        <div className="container">
          <div className="hero-eyebrow">
            <span className="badge badge-brand">Phase 6 Production Qualified</span>
          </div>
          <h1 className="heading-display hero-title">
            Chat in{' '}
            <span className="text-gradient">Tamil or English</span>
            <br />with Brud AI
          </h1>
          <p className="hero-subtitle">
            An AI assistant grounded in evidence. Ask questions in Tamil, English, or Tanglish.
            Brud AI retrieves from curated knowledge sources before answering — and tells you
            when it does not have enough evidence.
          </p>
          <div className="hero-actions">
            <Link to="/chat" className="btn btn-primary btn-lg" id="hero-start-chat">
              Start Chat
            </Link>
            <Link to="/features" className="btn btn-secondary btn-lg" id="hero-explore-features">
              Explore Features
            </Link>
          </div>
        </div>
      </section>

      {/* ── What is Brud AI ── */}
      <section className="section section-sm" aria-labelledby="about-heading">
        <div className="container">
          <div className="section-header">
            <h2 id="about-heading" className="heading-2">What is Brud AI?</h2>
            <p>
              Brud AI is a purpose-built multilingual AI platform. It is designed to deliver
              grounded, responsible answers — not hallucinated responses. Every reply is
              evaluated for safety and traced through an audit log.
            </p>
          </div>
          <div className="grid-2">
            <div className="card">
              <div className="feature-icon" aria-hidden="true">🎯</div>
              <h3 className="feature-title">Evidence-Grounded Answers</h3>
              <p className="feature-desc">
                Brud AI uses Retrieval-Augmented Generation (RAG). Before answering, it searches
                curated knowledge sources and uses that evidence to form a response. If evidence
                is insufficient, it says so rather than guessing.
              </p>
            </div>
            <div className="card">
              <div className="feature-icon" aria-hidden="true">🌐</div>
              <h3 className="feature-title">Multilingual by Design</h3>
              <p className="feature-desc">
                Tamil and English are first-class languages. Tanglish (Tamil words written in
                English script) is normalized and always answered in Tamil. No language
                configuration required — the system detects your input automatically.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Core Capabilities ── */}
      <section className="section" aria-labelledby="capabilities-heading" ref={featuresRef}>
        <div className="container">
          <div className="section-header">
            <span className="badge badge-brand" style={{ marginBottom: 'var(--space-4)', display: 'inline-flex' }}>Current Capabilities</span>
            <h2 id="capabilities-heading" className="heading-2">What Brud AI Can Do</h2>
            <p>
              These capabilities reflect Phase 6 production-qualified functionality.
              Features listed as "Coming Soon" are planned for future phases.
            </p>
          </div>
          <div className="grid-3">
            {FEATURES.map((f) => (
              <article className="card" key={f.title}>
                <div className="feature-icon" aria-hidden="true">{f.icon}</div>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-desc">{f.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="section section-sm" style={{ background: 'rgba(103,101,232,0.03)', borderTop: '1px solid var(--color-border-subtle)', borderBottom: '1px solid var(--color-border-subtle)' }} aria-labelledby="flow-heading">
        <div className="container">
          <div className="section-header">
            <h2 id="flow-heading" className="heading-2">How It Works</h2>
            <p>Every message you send passes through a governed pipeline.</p>
          </div>
          <nav className="flow" aria-label="Request pipeline flow">
            {FLOW_STEPS.map((step, i) => (
              <div className="flow-step" key={i}>
                <div className={`flow-box${step.highlighted ? ' highlighted' : ''}`}>
                  {step.label}
                </div>
                {i < FLOW_STEPS.length - 1 && <div className="flow-arrow" aria-hidden="true" />}
              </div>
            ))}
          </nav>
          <div style={{ textAlign: 'center', marginTop: 'var(--space-8)' }}>
            <Link to="/how-it-works" className="btn btn-secondary">
              Read Full Architecture →
            </Link>
          </div>
        </div>
      </section>

      {/* ── Why Brud AI ── */}
      <section className="section" aria-labelledby="why-heading">
        <div className="container">
          <div className="section-header">
            <h2 id="why-heading" className="heading-2">Why Brud AI</h2>
          </div>
          <div className="grid-2">
            {[
              { icon: '🔒', title: 'Security First', desc: 'Admin and public surfaces are completely isolated. Backend authorization enforces all access controls — not just UI visibility.' },
              { icon: '📋', title: 'Governance & Audit', desc: 'Every response is logged, evaluated for safety, and traceable. Quality & approval workflows govern what knowledge enters the system.' },
              { icon: '🧩', title: 'Controlled Architecture', desc: 'Each component — inference, RAG, memory, tools — is independently governed. No black-box deployments.' },
              { icon: '🛠️', title: 'Production Qualified', desc: 'P6-01 through P6-12 checks have all passed. This is not a prototype — it is a production-gated release.' },
            ].map((item) => (
              <div className="card" key={item.title} style={{ display: 'flex', gap: 'var(--space-4)' }}>
                <div className="feature-icon" aria-hidden="true" style={{ flexShrink: 0 }}>{item.icon}</div>
                <div>
                  <h3 className="feature-title">{item.title}</h3>
                  <p className="feature-desc" style={{ margin: 0 }}>{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ Teaser ── */}
      <section className="section section-sm" aria-labelledby="faq-teaser-heading">
        <div className="container">
          <div className="section-header">
            <h2 id="faq-teaser-heading" className="heading-2">Common Questions</h2>
          </div>
          <div className="faq-list">
            {FAQS.map((item) => (
              <div className="card" key={item.q} style={{ padding: 'var(--space-5)' }}>
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 700, marginBottom: 'var(--space-2)', color: 'var(--color-text-primary)' }}>
                  {item.q}
                </h3>
                <p style={{ margin: 0, color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', lineHeight: 1.65 }}>
                  {item.a}
                </p>
              </div>
            ))}
          </div>
          <div style={{ textAlign: 'center', marginTop: 'var(--space-8)' }}>
            <Link to="/faq" className="btn btn-secondary">View All FAQ →</Link>
          </div>
        </div>
      </section>

      {/* ── Desktop Teaser ── */}
      <section className="section section-sm" aria-labelledby="desktop-teaser-heading">
        <div className="container">
          <div className="cta-section">
            <span className="badge badge-warning" style={{ marginBottom: 'var(--space-4)', display: 'inline-flex' }}>Coming Soon</span>
            <h2 id="desktop-teaser-heading" className="heading-2" style={{ marginBottom: 'var(--space-4)' }}>
              Brud AI Desktop App
            </h2>
            <p style={{ color: 'var(--color-text-secondary)', maxWidth: 480, marginInline: 'auto', marginBottom: 'var(--space-8)' }}>
              A native desktop application is planned. It will bring Brud AI directly to
              your computer — offline-capable and locally controlled.
            </p>
            <Link to="/desktop" className="btn btn-secondary">Learn More →</Link>
          </div>
        </div>
      </section>

      {/* ── Primary CTA ── */}
      <section className="section" aria-labelledby="cta-heading">
        <div className="container">
          <div className="cta-section">
            <h2 id="cta-heading" className="heading-2" style={{ marginBottom: 'var(--space-4)' }}>
              Ready to start?
            </h2>
            <p style={{ color: 'var(--color-text-secondary)', maxWidth: 440, marginInline: 'auto', marginBottom: 'var(--space-8)' }}>
              Open the chat and ask Brud AI a question in Tamil or English.
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link to="/chat" className="btn btn-primary btn-lg" id="cta-start-chat">Start Chat</Link>
              <Link to="/help" className="btn btn-secondary btn-lg">Getting Started Guide</Link>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
