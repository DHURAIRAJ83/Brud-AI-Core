import { Link } from 'react-router-dom'

const STEPS = [
  {
    label: 'You',
    detail: 'You enter a question or message in Tamil, English, or Tanglish.',
    highlighted: false,
  },
  {
    label: 'Public Chat Interface',
    detail: 'Your input is sent to the Brud AI backend via a secure API call.',
    highlighted: true,
  },
  {
    label: 'Request Processing',
    detail: 'The backend validates the request, applies rate limiting, and determines the appropriate processing route.',
    highlighted: false,
  },
  {
    label: 'Language Detection',
    detail: 'The system detects whether the input is Tamil, English, or Tanglish and normalizes accordingly.',
    highlighted: false,
  },
  {
    label: 'Knowledge Routing',
    detail: 'The query is routed to the appropriate knowledge handler: RAG (knowledge base), trusted web retrieval, deterministic tools, or the core model.',
    highlighted: true,
  },
  {
    label: 'Retrieval (RAG)',
    detail: 'If applicable, relevant documents and evidence are retrieved from the curated knowledge base.',
    highlighted: false,
  },
  {
    label: 'Core Model',
    detail: 'The language model generates a response using the retrieved context.',
    highlighted: true,
  },
  {
    label: 'Safety Evaluation',
    detail: 'The response is evaluated for content safety before being returned.',
    highlighted: false,
  },
  {
    label: 'Audit Logging',
    detail: 'The request and response are logged in an immutable audit trail.',
    highlighted: false,
  },
  {
    label: 'Response to You',
    detail: 'The grounded, evaluated response is returned to the chat interface.',
    highlighted: true,
  },
]

export default function HowItWorksPage() {
  return (
    <>
      <div style={{ padding: 'var(--space-16) 0 var(--space-10)', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="container">
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>How It Works</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            Every message you send passes through a governed pipeline designed for
            accuracy, safety, and traceability.
          </p>
        </div>
      </div>

      <section className="section-sm">
        <div className="container">
          <div className="grid-2" style={{ alignItems: 'start', gap: 'var(--space-8)' }}>

            {/* Flow diagram */}
            <div>
              <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-8)', color: 'var(--color-text-accent)' }}>
                Request Pipeline
              </h2>
              <nav className="flow" style={{ maxWidth: '100%' }} aria-label="Request processing pipeline">
                {STEPS.map((step, i) => (
                  <div className="flow-step" key={i}>
                    <div className={`flow-box${step.highlighted ? ' highlighted' : ''}`}>
                      {step.label}
                    </div>
                    {i < STEPS.length - 1 && <div className="flow-arrow" aria-hidden="true" />}
                  </div>
                ))}
              </nav>
            </div>

            {/* Step explanations */}
            <div>
              <h2 style={{ fontSize: 'var(--font-size-xl)', marginBottom: 'var(--space-8)', color: 'var(--color-text-accent)' }}>
                Pipeline Details
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                {STEPS.map((step, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      gap: 'var(--space-4)',
                      padding: 'var(--space-4)',
                      background: step.highlighted ? 'rgba(103,101,232,0.06)' : 'var(--color-bg-card)',
                      border: `1px solid ${step.highlighted ? 'rgba(103,101,232,0.3)' : 'var(--color-border)'}`,
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <div style={{
                      flexShrink: 0,
                      width: 28,
                      height: 28,
                      borderRadius: 'var(--radius-full)',
                      background: step.highlighted ? 'var(--color-brand-500)' : 'var(--color-border)',
                      display: 'grid',
                      placeItems: 'center',
                      fontSize: 'var(--font-size-xs)',
                      fontWeight: 700,
                      color: 'white',
                    }}>{i + 1}</div>
                    <div>
                      <p style={{ margin: '0 0 var(--space-1)', fontWeight: 700, fontSize: 'var(--font-size-sm)', color: step.highlighted ? 'var(--color-text-accent)' : 'var(--color-text-primary)' }}>
                        {step.label}
                      </p>
                      <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
                        {step.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Privacy note */}
          <div className="notice notice-info" style={{ marginTop: 'var(--space-16)', maxWidth: 720, marginInline: 'auto' }}>
            <strong style={{ color: 'var(--color-text-accent)' }}>Privacy note: </strong>
            Implementation-sensitive security details are not disclosed publicly.
            Internal credentials, infrastructure paths, database schemas, and admin-only
            mechanisms are not exposed through the public interface.
          </div>

          {/* Knowledge routing detail */}
          <div style={{ marginTop: 'var(--space-16)' }}>
            <h2 className="heading-2" style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>Knowledge Routes</h2>
            <div className="grid-2">
              {[
                {
                  icon: '📚',
                  title: 'Approved RAG',
                  desc: 'The primary route for most queries. Retrieves from curated, approved knowledge sources.',
                  badge: 'Default',
                  badgeClass: 'badge-brand',
                },
                {
                  icon: '🌐',
                  title: 'Trusted Web',
                  desc: 'For queries outside the knowledge base, retrieval from trusted web sources is attempted.',
                  badge: 'Secondary',
                  badgeClass: 'badge-muted',
                },
                {
                  icon: '⚙️',
                  title: 'Deterministic Tools',
                  desc: 'Specific query types are handled by deterministic tools for reliable, non-probabilistic answers.',
                  badge: 'Specialized',
                  badgeClass: 'badge-muted',
                },
                {
                  icon: '🤖',
                  title: 'Core Model',
                  desc: 'The language model is consulted after context retrieval. It does not operate in isolation.',
                  badge: 'Always Present',
                  badgeClass: 'badge-muted',
                },
              ].map((item) => (
                <div className="card" key={item.title}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
                    <div className="feature-icon" aria-hidden="true" style={{ marginBottom: 0 }}>{item.icon}</div>
                    <span className={`badge ${item.badgeClass}`}>{item.badge}</span>
                  </div>
                  <h3 className="feature-title">{item.title}</h3>
                  <p className="feature-desc" style={{ margin: 0 }}>{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div style={{ textAlign: 'center', marginTop: 'var(--space-12)' }}>
            <Link to="/chat" className="btn btn-primary btn-lg">Start Chat</Link>
            <Link to="/features" className="btn btn-secondary btn-lg" style={{ marginLeft: 'var(--space-4)' }}>View All Features</Link>
          </div>
        </div>
      </section>
    </>
  )
}
