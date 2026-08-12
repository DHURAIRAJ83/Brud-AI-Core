export default function FutureModelTab() {
  return (
    <div className="notice">
      <p>Brud AI now has a real local LLM runtime, added after this tab was first written in MB-01 --
      it lives across three other tabs, not here:</p>
      <ul>
        <li><b>Local Setup</b> -- detects your hardware and recommends a CPU-friendly GGUF model for it.</li>
        <li><b>Runtime Manager</b> -- installs, loads, unloads, and benchmarks that model with real RAM
        and disk guards before anything loads.</li>
        <li><b>Assistant Intelligence</b> -- where admin conversations actually run once a model is loaded,
        with a governed external-provider fallback configured separately in <b>Provider Settings</b>.</li>
      </ul>
      <p>The runtime is CPU-first -- no GPU is required -- and once a GGUF model is installed, it can
      answer entirely offline with no external network call.</p>
      <p>This tab's own five endpoints below are unrelated MB-01-era extension points, kept as
      documented placeholders and unchanged in shape -- they are not part of the real runtime above:</p>
      <ul>
        <li><code>POST /api/admin/mini-brain/inference</code> -- currently returns <code>available: false</code></li>
        <li><code>GET /api/admin/mini-brain/knowledge</code> -- currently returns <code>available: false</code></li>
        <li><code>GET /api/admin/mini-brain/memory</code> -- currently returns <code>available: false</code></li>
        <li><code>POST /api/admin/mini-brain/suggestions</code> -- currently returns <code>available: false</code></li>
        <li><code>GET /api/admin/mini-brain/context</code> -- Brud Context Interface, currently returns <code>available: false</code>; reserved for MB-02's Admin Dashboard / dataset / training / RAG workflow context provider</li>
      </ul>
    </div>
  )
}
