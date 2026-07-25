export const menuItems = ['Overview', 'System', 'Datasets', 'Documents', 'Tokenizer', 'Core Model', 'Training', 'Base Training', 'Instruction Tuning', 'Evaluation', 'Model Registry', 'Inference Runtime', 'Knowledge & RAG', 'Conversation & Memory', 'Feedback & Improvement', 'Corpus Builder', 'Chat Testing', 'Admin Assistant', 'Audit Logs', 'Settings']

export default function Sidebar({ active, open, onSelect, onClose }) {
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="side-brand"><span>B</span><div><strong>Brud AI</strong><small>Control center</small></div></div>
      <nav aria-label="Admin modules">{menuItems.map((item) => (
        <button className={active === item ? 'active' : ''} key={item} onClick={() => { onSelect(item); onClose() }}>{item}</button>
      ))}</nav>
      <div className="phase-tag">Phase 19 · Tamil corpus builder</div>
    </aside>
  )
}
