import React from 'react'

export default function MiniBrainGuideTab({ onNavigate }) {
  return (
    <div className="mini-brain-guide-tab" style={{ padding: '1rem', maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.08))', paddingBottom: '1rem' }}>
        <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1.5rem', color: 'var(--text-primary)' }}>
          🧠 Brud Mini Brain & Admin Assistant Intelligence Guide
        </h2>
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: '1.5' }}>
          Mini Brain functions as the central Admin Intelligence Layer for the Brud AI platform, providing system-wide context awareness, controlled model routing, dataset generation, and automated post-training evaluation.
        </p>
      </div>

      <div className="guide-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        <div className="card" style={{ padding: '1rem', background: 'var(--bg-card, #161622)', borderRadius: '8px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--primary, #38bdf8)' }}>
            1. What can Mini Brain see?
          </h3>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            Mini Brain has real-time, read-only visibility into the entire dashboard via <code>GET /api/admin/mini-brain/context</code>: System Health, Configured Providers, Models, Datasets, Training Runs, Evaluations, RAG spaces, Memory, Governance proposals, and Audit Logs. Secrets and API keys are never exposed.
          </p>
        </div>

        <div className="card" style={{ padding: '1rem', background: 'var(--bg-card, #161622)', borderRadius: '8px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--primary, #38bdf8)' }}>
            2. Local vs. Provider Models
          </h3>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            <strong>Local Models:</strong> Hosted via Ollama/llama.cpp for offline, private, zero-cost inference.
            <br />
            <strong>External Providers:</strong> OpenRouter, OpenAI, Anthropic, Gemini for complex reasoning, synthetic dataset creation, and heavy benchmark analysis.
          </p>
        </div>

        <div className="card" style={{ padding: '1rem', background: 'var(--bg-card, #161622)', borderRadius: '8px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--primary, #38bdf8)' }}>
            3. RAG Grounding & Retrieval
          </h3>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            When &ldquo;Knowledge Base&rdquo; is enabled, user queries retrieve approved knowledge chunks through vector and keyword indexes. Mini Brain cites sources with exact ranks and confidence scores.
          </p>
        </div>

        <div className="card" style={{ padding: '1rem', background: 'var(--bg-card, #161622)', borderRadius: '8px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--primary, #38bdf8)' }}>
            4. Dataset Generation (MB-16)
          </h3>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            Execute 10-stage dataset generation directly from the Chat &ldquo;Generate&rdquo; tab. Generated records remain Draft until Admin certification before passing to RAG or pre-training queues.
          </p>
        </div>

        <div className="card" style={{ padding: '1rem', background: 'var(--bg-card, #161622)', borderRadius: '8px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--primary, #38bdf8)' }}>
            5. Automated Evaluation Engine
          </h3>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            Post-training triggers a 17-category evaluation suite (Tamil/English quality, reasoning, hallucination resistance, safety, latency) comparing candidate models against baseline models with automated regression detection.
          </p>
        </div>

        <div className="card" style={{ padding: '1rem', background: 'var(--bg-card, #161622)', borderRadius: '8px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--primary, #38bdf8)' }}>
            6. Governance & Approval Gates
          </h3>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            Mini Brain authority is strictly <code>ADVISORY_ONLY</code>. Dangerous operations follow <em>PROPOSE → REVIEW → APPROVE → EXECUTE</em>. Model training and production promotion are fail-closed.
          </p>
        </div>
      </div>

      <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(56, 189, 248, 0.05)', borderRadius: '8px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
        <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--primary, #38bdf8)' }}>Quick Navigation Links</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {onNavigate && (
            <>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => onNavigate('Data')}>Data Workspace</button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => onNavigate('RAG')}>RAG Sandbox</button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => onNavigate('Models')}>Model Registry</button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => onNavigate('Training')}>Training Engine</button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => onNavigate('Governance')}>Governance Center</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
