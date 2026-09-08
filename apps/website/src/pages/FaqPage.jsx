import { useState } from 'react'
import { Link } from 'react-router-dom'

const FAQS = [
  {
    q: 'What is Brud AI?',
    a: 'Brud AI is a multilingual AI chat assistant that supports Tamil and English (including Tanglish). It uses Retrieval-Augmented Generation (RAG) to provide evidence-grounded answers and tells you when it does not have enough evidence to answer confidently.',
  },
  {
    q: 'How do I start chatting?',
    a: 'Go to the Chat page and type your question in Tamil, English, or Tanglish. No account or sign-up is required for public chat in the current version.',
  },
  {
    q: 'Do I need an account?',
    a: 'No. Public chat does not require an account. Account-based features — such as persistent history across sessions — are planned for a future release.',
  },
  {
    q: 'Which languages are supported?',
    a: 'Tamil, English, and Tanglish (Tamil written in English script). Language detection is automatic. Tanglish input is always answered in Tamil.',
  },
  {
    q: 'What is RAG?',
    a: 'RAG stands for Retrieval-Augmented Generation. Before generating a response, Brud AI retrieves relevant documents from a curated knowledge base. The model then uses that retrieved evidence when formulating its answer, rather than relying purely on model memory.',
  },
  {
    q: 'Can Brud AI say it does not have enough evidence?',
    a: 'Yes. This is an intentional design feature. When the system does not find sufficient evidence to answer confidently, it will say so rather than generating a plausible-sounding but unsupported response.',
  },
  {
    q: 'Is the admin dashboard accessible from this website?',
    a: 'No. The admin dashboard is a completely separate application, accessible only through its own dedicated origin. It is not linked from this public website and requires authentication. Admin access is enforced at the backend — hiding the link is not the security boundary.',
  },
  {
    q: 'Is a desktop application available?',
    a: 'A desktop application is planned but is not yet available for download. When it is ready, it will be listed on the Desktop App page.',
  },
  {
    q: 'What should I do if the service is unavailable?',
    a: 'If the chat service is not reachable, check the status indicator in the chat header. The service may be temporarily unavailable. Try again after a few minutes. If the issue persists, consult the Help page.',
  },
  {
    q: 'How does Brud AI handle privacy?',
    a: 'Public chat sessions are processed by the backend for response generation. No account data is stored by default in the current version. Refer to the Privacy page for current information. Finalized legal data retention policies will be documented when implemented.',
  },
  {
    q: 'Is Brud AI always correct?',
    a: 'No AI system is always correct. Brud AI is designed to be evidence-grounded and to indicate uncertainty, but responses can still be incomplete or incorrect. Do not rely on AI responses for critical medical, legal, financial, or safety decisions.',
  },
  {
    q: 'What tools does Brud AI have access to?',
    a: 'Brud AI has access to deterministic tools for specific query types, trusted web retrieval for queries outside the knowledge base, and its curated knowledge base for RAG. Tool access is governed and audited.',
  },
  {
    q: 'How do I report a problem?',
    a: 'Use the feedback controls in the chat interface (Helpful / Not helpful / Wrong language / Unsafe). These reports feed into quality monitoring. For general issues, refer to the Help page.',
  },
]

function FaqItem({ item }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="faq-item" data-open={open ? 'true' : 'false'}>
      <button
        className="faq-question"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        id={`faq-q-${item.q.slice(0, 20).replace(/\s+/g, '-').toLowerCase()}`}
      >
        {item.q}
        <span className="faq-chevron" aria-hidden="true">▾</span>
      </button>
      <div
        className="faq-answer"
        role="region"
        aria-labelledby={`faq-q-${item.q.slice(0, 20).replace(/\s+/g, '-').toLowerCase()}`}
      >
        {item.a}
      </div>
    </div>
  )
}

export default function FaqPage() {
  return (
    <>
      <div style={{ padding: 'var(--space-16) 0 var(--space-10)', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="container">
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>Frequently Asked Questions</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 520, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            Common questions about Brud AI. If you do not find what you need, visit the{' '}
            <Link to="/help">Help page</Link>.
          </p>
        </div>
      </div>

      <section className="section-sm">
        <div className="container">
          <div className="faq-list" role="list">
            {FAQS.map((item) => (
              <FaqItem key={item.q} item={item} />
            ))}
          </div>

          <div style={{ textAlign: 'center', marginTop: 'var(--space-12)' }}>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-6)' }}>
              Still have questions?
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link to="/help" className="btn btn-primary">Getting Started Guide</Link>
              <Link to="/chat" className="btn btn-secondary">Open Chat</Link>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
