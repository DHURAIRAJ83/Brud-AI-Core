import { useState } from 'react'

// Presentation-only, data-shape-agnostic: each caller (Mini Brain Chat's
// lrSessions shape, Public Chat Monitor's pcrSessions shape) maps its own
// real API response into { id, title, subtitle, meta, status } before
// passing it in. Search here is real client-side filtering over already-
// fetched items -- no server-side search endpoint exists to call.
export default function SessionList({ items, activeId, onSelect, onDelete, emptyLabel = 'No sessions yet.' }) {
  const [search, setSearch] = useState('')

  const filtered = items.filter((item) => {
    if (!search.trim()) return true
    const haystack = `${item.title ?? ''} ${item.subtitle ?? ''}`.toLowerCase()
    return haystack.includes(search.trim().toLowerCase())
  })

  return (
    <div className="session-list">
      <input
        type="search"
        aria-label="Search conversations"
        placeholder="Search conversations…"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      {filtered.length === 0 ? (
        <div className="notice">{items.length === 0 ? emptyLabel : 'No conversations match this search.'}</div>
      ) : (
        <ul>
          {filtered.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={item.id === activeId ? 'active' : ''}
                aria-current={item.id === activeId ? 'true' : undefined}
                onClick={() => onSelect(item.id)}
              >
                <strong>{item.title}</strong>
                {item.status && <span className="session-status">{item.status}</span>}
                {item.subtitle && <small>{item.subtitle}</small>}
                {item.meta && <small className="session-meta">{item.meta}</small>}
              </button>
              {onDelete && (
                <button type="button" className="session-delete" aria-label={`Delete ${item.title}`} onClick={() => onDelete(item.id)}>
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
