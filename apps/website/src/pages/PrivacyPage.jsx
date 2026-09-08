import { Link } from 'react-router-dom'

// Privacy page — informational only.
// This is NOT finalized legal policy.
// Data retention policy is not finalized; we do not state a retention number.

export default function PrivacyPage() {
  return (
    <>
      <div style={{ padding: 'var(--space-16) 0 var(--space-10)', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="container">
          <h1 className="heading-1" style={{ marginBottom: 'var(--space-4)' }}>Privacy Information</h1>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, marginInline: 'auto', fontSize: 'var(--font-size-lg)' }}>
            How your information is handled when you use Brud AI.
          </p>
          <div className="notice notice-info" style={{ maxWidth: 640, marginInline: 'auto', marginTop: 'var(--space-6)' }}>
            <strong style={{ color: 'var(--color-text-accent)' }}>Note: </strong>
            This is an informational page, not a finalized legal privacy policy.
            It reflects the current implementation as of Phase 6.
          </div>
        </div>
      </div>

      <section className="section-sm">
        <div className="container">
          <div className="prose">

            <h2>Public Chat</h2>
            <p>
              Brud AI's public chat is accessible without an account. When you send a message,
              it is transmitted to the Brud AI backend server for processing. The backend
              uses your message to retrieve relevant knowledge and generate a response.
            </p>
            <p>
              Messages are not shared with third parties for commercial purposes. Knowledge
              retrieval uses curated internal sources and, where applicable, trusted web sources.
            </p>

            <h2>What Information Is Processed</h2>
            <ul>
              <li>Your chat messages (to generate responses)</li>
              <li>Your selected language preference (if set manually)</li>
              <li>Your session identifier (temporary, within-session only in the current implementation)</li>
              <li>Technical metadata: IP address, timestamp, and request identifiers (for rate limiting, audit, and monitoring)</li>
            </ul>
            <p>
              No name, email, or personal account data is collected in anonymous public chat.
            </p>

            <h2>Conversation and Session Handling</h2>
            <p>
              In the current implementation, conversation context is maintained within a single
              session. If you opt in to memory (via the checkbox in the chat interface), the
              system associates messages with a session identifier for the duration of that session.
            </p>
            <p>
              Persistent cross-session history linked to a user account is not available in this
              phase. This feature is planned for a future release.
            </p>

            <h2>Audit Logging</h2>
            <p>
              Brud AI maintains an audit log of system events for operational, safety, and
              governance purposes. This log is internal and not publicly accessible. It is used
              to monitor system health, investigate issues, and enforce quality governance.
            </p>

            <h2>Data Retention</h2>
            <div className="notice notice-info">
              Retention policy is being finalized. No specific retention period can be stated
              at this stage. This page will be updated when a finalized retention policy is
              implemented and verified.
            </div>

            <h2>Future Account Features</h2>
            <p>
              A future phase will introduce user accounts. When accounts are implemented,
              a separate, updated privacy policy will be published to cover account-specific
              data handling, including history, preferences, and deletion rights.
            </p>

            <h2>Admin Access</h2>
            <p>
              Admin access to the Brud AI platform is completely separate from public chat.
              Admin credentials are not accessible to public users. The admin interface is
              not linked from the public website. Backend authorization enforces all admin access.
            </p>

            <h2>External Links</h2>
            <p>
              Where the system uses trusted web retrieval, links to external sources may
              appear in responses. Brud AI is not responsible for the privacy practices of
              external websites.
            </p>

            <h2>Contact</h2>
            <p>
              For questions about data handling, use the feedback mechanism in the chat
              interface or refer to the <Link to="/help">Help page</Link>.
            </p>
          </div>
        </div>
      </section>
    </>
  )
}
