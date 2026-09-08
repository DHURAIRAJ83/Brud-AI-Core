import { Link } from 'react-router-dom'

const STEPS = [
  {
    title: 'Open Chat',
    detail: 'Navigate to the Chat page. No account or sign-in is required for public chat.',
    action: <Link to="/chat" className="btn btn-primary btn-sm">Open Chat →</Link>,
  },
  {
    title: 'Enter Your Question',
    detail: 'Type your question or message in the input box at the bottom of the screen. You can write in Tamil, English, or Tanglish.',
    action: null,
  },
  {
    title: 'Send the Message',
    detail: 'Press Enter or click the Send button. Your message is sent to the Brud AI backend.',
    action: null,
  },
  {
    title: 'Read the Response',
    detail: 'Brud AI will retrieve relevant evidence and generate a grounded response. The route label (RAG, Web, Tool, etc.) shows which knowledge route was used.',
    action: null,
  },
  {
    title: 'Ask a Follow-up',
    detail: 'The system maintains conversation context within your session. You can ask follow-up questions without restating your context.',
    action: null,
  },
  {
    title: 'Use Available Features',
    detail: 'You can select a language override (Tamil / English / Auto) if needed. You can also opt in to session memory using the checkbox below the chat.',
    action: null,
  },
  {
    title: 'Provide Feedback',
    detail: 'If a response is helpful, unhelpful, wrong language, or unsafe — use the feedback buttons below each response. This helps improve quality.',
    action: null,
  },
]

const LIMITATIONS = [
  'AI responses are not guaranteed to be accurate. Always verify important information.',
  'Brud AI will sometimes say it does not have enough evidence to answer. This is intentional and correct behavior.',
  'The system is designed for informational purposes. Do not rely on it for medical, legal, financial, or safety-critical decisions.',
  'Service may occasionally be unavailable. The health indicator in the chat header shows the current status.',
  'Language detection is automatic but may occasionally misidentify short or ambiguous inputs.',
]

export default function HelpPage() {
  return (
    <>
      <div style={{ padding: 'var(--space-16) 0 var(--space-10)', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="container">
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>Getting Started</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 520, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            How to use Brud AI. Follow these steps to start your first conversation.
          </p>
        </div>
      </div>

      <section className="section-sm">
        <div className="container">

          {/* Steps */}
          <h2 style={{ fontSize: 'var(--font-size-2xl)', marginBottom: 'var(--space-8)', textAlign: 'center' }}>
            Step-by-Step Guide
          </h2>
          <ol className="steps" style={{ listStyle: 'none', padding: 0, margin: '0 auto' }}>
            {STEPS.map((step, i) => (
              <li className="step" key={i}>
                <div className="step-number" aria-label={`Step ${i + 1}`}>{i + 1}</div>
                <div className="step-content">
                  <h3>{step.title}</h3>
                  <p>{step.detail}</p>
                  {step.action && <div style={{ marginTop: 'var(--space-3)' }}>{step.action}</div>}
                </div>
              </li>
            ))}
          </ol>

          {/* Current vs Future */}
          <div style={{ marginTop: 'var(--space-16)' }}>
            <h2 className="heading-2" style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
              Current vs. Future Features
            </h2>
            <div className="grid-2">
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                  <span className="badge badge-success">Available Now</span>
                </div>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-5)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', lineHeight: 1.8 }}>
                  <li>Public chat — no account required</li>
                  <li>Tamil, English, and Tanglish input</li>
                  <li>RAG-grounded responses</li>
                  <li>Trusted web retrieval</li>
                  <li>Deterministic tools</li>
                  <li>Session memory (opt-in)</li>
                  <li>Insufficient-evidence handling</li>
                  <li>Feedback controls</li>
                  <li>Content safety evaluation</li>
                  <li>Health monitoring</li>
                </ul>
              </div>
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                  <span className="badge badge-warning">Coming Soon</span>
                </div>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-5)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', lineHeight: 1.8 }}>
                  <li>User accounts and persistent history</li>
                  <li>Cross-session memory</li>
                  <li>Desktop application (macOS, Windows, Linux)</li>
                  <li>Expanded language support</li>
                  <li>Mobile application</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Limitations */}
          <div style={{ marginTop: 'var(--space-16)' }}>
            <h2 className="heading-2" style={{ marginBottom: 'var(--space-6)', textAlign: 'center' }}>
              Important Limitations
            </h2>
            <div className="card" style={{ maxWidth: 720, marginInline: 'auto' }}>
              <ul style={{ margin: 0, paddingLeft: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {LIMITATIONS.map((l, i) => (
                  <li key={i} style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', lineHeight: 1.65 }}>{l}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Reporting issues */}
          <div style={{ marginTop: 'var(--space-16)' }}>
            <h2 className="heading-2" style={{ marginBottom: 'var(--space-6)', textAlign: 'center' }}>
              Reporting Issues
            </h2>
            <div className="card" style={{ maxWidth: 720, marginInline: 'auto' }}>
              <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
                If you encounter a response that is incorrect, unsafe, in the wrong language,
                or otherwise problematic:
              </p>
              <ol style={{ paddingLeft: 'var(--space-5)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', lineHeight: 1.8, margin: 0 }}>
                <li>Use the feedback buttons below the response (Helpful / Not helpful / Wrong language / Unsafe)</li>
                <li>Include context if possible by submitting via the feedback comment field</li>
                <li>Check the <Link to="/faq">FAQ</Link> for common issues</li>
                <li>If the service is unreachable, check the health indicator in the chat header</li>
              </ol>
            </div>
          </div>

          <div style={{ textAlign: 'center', marginTop: 'var(--space-12)' }}>
            <Link to="/chat" className="btn btn-primary btn-lg">Open Chat Now</Link>
            <Link to="/faq" className="btn btn-secondary btn-lg" style={{ marginLeft: 'var(--space-4)' }}>View FAQ</Link>
          </div>
        </div>
      </section>
    </>
  )
}
