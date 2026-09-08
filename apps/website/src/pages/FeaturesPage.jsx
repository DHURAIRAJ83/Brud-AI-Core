import { Link } from 'react-router-dom'

const FEATURES = [
  {
    category: 'AI Chat',
    status: 'available',
    icon: '💬',
    title: 'Conversational AI',
    what: 'Ask questions and receive coherent, context-aware replies.',
    why: 'Natural language interaction reduces friction for all users.',
    benefit: 'Get answers quickly without needing technical knowledge.',
  },
  {
    category: 'Language',
    status: 'available',
    icon: 'அ',
    title: 'Tamil Language Support',
    what: 'Full support for Tamil-language questions and responses.',
    why: 'Tamil is an underserved language in AI. Brud AI treats it as a first-class input.',
    benefit: 'Chat naturally in Tamil — no transliteration required.',
  },
  {
    category: 'Language',
    status: 'available',
    icon: 'Aa',
    title: 'English Language Support',
    what: 'Full support for English questions and responses.',
    why: 'English is the primary technical and professional language for many users.',
    benefit: 'Use the same system for both Tamil and English without switching tools.',
  },
  {
    category: 'Language',
    status: 'available',
    icon: '🔤',
    title: 'Tanglish Input Normalization',
    what: 'Tamil words written in English script (Tanglish) are detected and normalized.',
    why: 'Many Tamil speakers type in English script online. Brud AI understands this.',
    benefit: 'Type naturally — Tanglish input is always answered in Tamil.',
  },
  {
    category: 'Knowledge',
    status: 'available',
    icon: '📚',
    title: 'RAG — Retrieval-Augmented Generation',
    what: 'Before answering, Brud AI searches curated knowledge sources and retrieves relevant evidence.',
    why: 'Pure language model output can hallucinate. RAG grounds responses in actual content.',
    benefit: 'Answers are backed by retrievable evidence, not pure model memory.',
  },
  {
    category: 'Knowledge',
    status: 'available',
    icon: '🔍',
    title: 'Insufficient Evidence Handling',
    what: 'When Brud AI does not have enough evidence to answer, it says so explicitly.',
    why: 'Honest uncertainty is more valuable than confident hallucination.',
    benefit: 'You know when to seek additional sources rather than trusting a fabricated answer.',
  },
  {
    category: 'Knowledge',
    status: 'available',
    icon: '🌐',
    title: 'Trusted Web Retrieval',
    what: 'For queries outside the knowledge base, Brud AI can retrieve from trusted web sources.',
    why: 'Static knowledge bases become outdated. Controlled web access extends coverage.',
    benefit: 'Recent and specialized information can be retrieved where applicable.',
  },
  {
    category: 'Memory',
    status: 'available',
    icon: '🧠',
    title: 'Conversation Memory (Opt-in)',
    what: 'Conversation context is maintained within a session. Opt-in memory allows continuity.',
    why: 'Follow-up questions require context. Memory prevents you from repeating yourself.',
    benefit: 'Ask follow-up questions without re-explaining your context.',
  },
  {
    category: 'Security',
    status: 'available',
    icon: '🛡️',
    title: 'Content Safety Evaluation',
    what: 'Every response is evaluated for safety before being returned.',
    why: 'AI systems can produce unsafe content without governance. Safety evaluation is not optional.',
    benefit: 'Responses go through safety checks before reaching you.',
  },
  {
    category: 'Security',
    status: 'available',
    icon: '📋',
    title: 'Audit Logging',
    what: 'All significant actions are logged in an immutable audit trail.',
    why: 'Accountability requires traceability. Audit logs enable investigation of issues.',
    benefit: 'The system is accountable — every response is traceable.',
  },
  {
    category: 'Monitoring',
    status: 'available',
    icon: '📊',
    title: 'Health & Operational Status',
    what: 'Service health, readiness, and operational status are monitored continuously.',
    why: 'Users need to know when the service is degraded or unavailable.',
    benefit: 'The chat interface displays real-time service health.',
  },
  {
    category: 'Tools',
    status: 'available',
    icon: '⚙️',
    title: 'Deterministic Tools',
    what: 'For specific query types, Brud AI can invoke deterministic tools that produce reliable structured results.',
    why: 'Some questions have precise answers that should not be left to probabilistic generation.',
    benefit: 'Calculations and structured queries get deterministic, reliable answers.',
  },
  {
    category: 'Desktop',
    status: 'coming-soon',
    icon: '🖥️',
    title: 'Desktop Application',
    what: 'A native desktop application for macOS, Windows, and Linux.',
    why: 'A desktop app enables offline operation and tighter OS integration.',
    benefit: 'Use Brud AI without a browser, with locally controlled data.',
  },
  {
    category: 'Account',
    status: 'coming-soon',
    icon: '👤',
    title: 'User Accounts',
    what: 'Personal accounts for persisted history and preferences.',
    why: 'Anonymous sessions do not persist across devices or restarts.',
    benefit: 'Your conversation history and preferences follow you across sessions.',
  },
]

const CATEGORIES = [...new Set(FEATURES.map((f) => f.category))]

export default function FeaturesPage() {
  return (
    <>
      <div className="page-hero" style={{ padding: 'var(--space-16) 0 var(--space-10)' }}>
        <div className="container">
          <span className="badge badge-brand" style={{ marginBottom: 'var(--space-4)', display: 'inline-flex' }}>
            Phase 6 Production Qualified
          </span>
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>Features</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            All features listed below are based on verified repository functionality.
            Features marked <span className="badge badge-warning" style={{ display: 'inline-flex', verticalAlign: 'middle' }}>Coming Soon</span> are planned for future phases.
          </p>
        </div>
      </div>

      <section className="section-sm">
        <div className="container">
          {CATEGORIES.map((category) => {
            const items = FEATURES.filter((f) => f.category === category)
            return (
              <div key={category} style={{ marginBottom: 'var(--space-16)' }}>
                <h2 style={{ fontSize: 'var(--font-size-2xl)', marginBottom: 'var(--space-8)', paddingBottom: 'var(--space-4)', borderBottom: '1px solid var(--color-border-subtle)', display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  {category}
                </h2>
                <div className="grid-2">
                  {items.map((f) => (
                    <article className="card" key={f.title} style={{ position: 'relative', overflow: 'hidden' }}>
                      {f.status === 'coming-soon' && (
                        <span className="badge badge-warning" style={{ position: 'absolute', top: 'var(--space-4)', right: 'var(--space-4)' }}>
                          Coming Soon
                        </span>
                      )}
                      {f.status === 'available' && (
                        <span className="badge badge-success" style={{ position: 'absolute', top: 'var(--space-4)', right: 'var(--space-4)' }}>
                          Available
                        </span>
                      )}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
                        <div className="feature-icon" aria-hidden="true" style={{ marginBottom: 0, fontSize: f.icon.length > 1 ? '1.2rem' : '1.4rem' }}>{f.icon}</div>
                        <h3 className="feature-title" style={{ paddingTop: 'var(--space-2)', marginBottom: 0 }}>{f.title}</h3>
                      </div>
                      <dl style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', margin: 0 }}>
                        <div>
                          <dt style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>What</dt>
                          <dd style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>{f.what}</dd>
                        </div>
                        <div>
                          <dt style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>Why</dt>
                          <dd style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>{f.why}</dd>
                        </div>
                        <div>
                          <dt style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>Benefit</dt>
                          <dd style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>{f.benefit}</dd>
                        </div>
                      </dl>
                    </article>
                  ))}
                </div>
              </div>
            )
          })}

          <div className="cta-section">
            <h2 className="heading-2" style={{ marginBottom: 'var(--space-4)' }}>Ready to experience these features?</h2>
            <div style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link to="/chat" className="btn btn-primary btn-lg">Start Chat</Link>
              <Link to="/how-it-works" className="btn btn-secondary btn-lg">How It Works</Link>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
