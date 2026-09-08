import { Link } from 'react-router-dom'

// Terms page — informational only.
// This is NOT finalized legal policy or legal advice.

export default function TermsPage() {
  return (
    <>
      <div style={{ padding: 'var(--space-16) 0 var(--space-10)', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="container">
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>Terms of Use</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            Guidelines for using Brud AI responsibly.
          </p>
          <div className="notice notice-info" style={{ maxWidth: 640, marginInline: 'auto', marginTop: 'var(--space-6)' }}>
            <strong style={{ color: 'var(--color-text-accent)' }}>Note: </strong>
            This is an informational page, not a finalized legal terms of service document.
            It reflects acceptable use guidelines for the current phase.
          </div>
        </div>
      </div>

      <section className="section-sm">
        <div className="container">
          <div className="prose">

            <h2>Responsible Use</h2>
            <p>
              Brud AI is an AI assistant designed to provide helpful, evidence-grounded responses
              in Tamil and English. You are expected to use it responsibly and in good faith.
            </p>

            <h2>No Guaranteed Correctness</h2>
            <p>
              AI responses are not guaranteed to be accurate, complete, or up-to-date.
              Brud AI is designed to indicate when evidence is insufficient, but it can still
              make mistakes. Always verify important information through authoritative sources.
            </p>
            <div className="notice notice-warning" style={{ marginBottom: 'var(--space-4)' }}>
              <strong>Do not rely on Brud AI responses for critical decisions</strong> in areas
              such as medicine, law, finance, safety, or any domain where errors could cause
              harm. AI responses are not professional advice.
            </div>

            <h2>Prohibited Use</h2>
            <p>The following uses are not permitted:</p>
            <ul>
              <li>Attempting to bypass safety evaluations or guardrails</li>
              <li>Generating or requesting harmful, abusive, illegal, or dangerous content</li>
              <li>Attempting to extract internal system information, credentials, or private infrastructure details</li>
              <li>Automated abuse, scraping, or excessive automated requests beyond the rate limits</li>
              <li>Attempting unauthorized access to admin or restricted functionality</li>
              <li>Misrepresenting AI-generated content as human-authored without disclosure</li>
              <li>Using the service to harass, deceive, or harm others</li>
            </ul>

            <h2>Service Availability</h2>
            <p>
              Service availability may vary. Brud AI may be temporarily unavailable for
              maintenance, updates, or infrastructure reasons. No uptime guarantee is made
              at this stage of development.
            </p>

            <h2>AI Limitations</h2>
            <p>
              Brud AI is an AI system with real limitations:
            </p>
            <ul>
              <li>It may not have knowledge of recent events beyond its knowledge base.</li>
              <li>It may misunderstand ambiguous questions.</li>
              <li>It may occasionally produce responses that are plausible but incorrect.</li>
              <li>It is designed to indicate uncertainty, but this mechanism is not infallible.</li>
            </ul>

            <h2>Feedback</h2>
            <p>
              If you receive a response that is unsafe, incorrect, or in the wrong language,
              use the feedback controls in the chat interface. Feedback is used for quality
              monitoring and improvement.
            </p>

            <h2>Changes to These Terms</h2>
            <p>
              These guidelines may be updated as Brud AI evolves. This page reflects the
              current state as of Phase 6 qualification.
            </p>

            <h2>Questions</h2>
            <p>
              For questions about usage, refer to the <Link to="/help">Help page</Link> or
              the <Link to="/faq">FAQ</Link>.
            </p>
          </div>
        </div>
      </section>
    </>
  )
}
