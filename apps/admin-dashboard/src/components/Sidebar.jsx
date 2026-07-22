export const menuItems = ['Overview', 'System', 'Datasets', 'Documents', 'Tokenizer', 'Core Model', 'Training', 'Evaluation', 'Model Registry', 'Chat Testing', 'Feedback', 'Admin Assistant', 'Audit Logs', 'Settings']

export default function Sidebar({ active, open, onSelect, onClose }) {
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="side-brand"><span>B</span><div><strong>Brud AI</strong><small>Control center</small></div></div>
      <nav aria-label="Admin modules">{menuItems.map((item) => (
        <button className={active === item ? 'active' : ''} key={item} onClick={() => { onSelect(item); onClose() }}>{item}</button>
      ))}</nav>
      <div className="phase-tag">Phase 7 · Tokenizer training</div>
    </aside>
  )
}
