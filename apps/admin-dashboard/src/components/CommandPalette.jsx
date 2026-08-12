import { useEffect, useMemo, useRef, useState } from 'react'
import { navTree } from './Sidebar.jsx'

// Flat, searchable index built once from the same navTree Sidebar renders
// -- no separate registry to keep in sync, no new routing plumbing (jumping
// to a result calls the same onSelect/selectPage path the Sidebar uses).
const SEARCH_ITEMS = navTree.flatMap((item) =>
  item.group
    ? item.children.map((child) => ({ key: child.key, label: child.ariaLabel ?? child.label, group: item.label }))
    : [{ key: item.key, label: item.label, group: null }]
)

function matches(item, query) {
  const haystack = query.toLowerCase()
  return item.label.toLowerCase().includes(haystack) || (item.group ?? '').toLowerCase().includes(haystack)
}

export default function CommandPalette({ onSelect }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)

  const results = useMemo(() => {
    if (!query.trim()) return SEARCH_ITEMS
    return SEARCH_ITEMS.filter((item) => matches(item, query))
  }, [query])

  useEffect(() => {
    function handleGlobalKeydown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', handleGlobalKeydown)
    return () => window.removeEventListener('keydown', handleGlobalKeydown)
  }, [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setActiveIndex(0)
      // Focus after the dialog mounts.
      const id = setTimeout(() => inputRef.current?.focus(), 0)
      return () => clearTimeout(id)
    }
  }, [open])

  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  function choose(key) {
    onSelect(key)
    setOpen(false)
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      setOpen(false)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => Math.min(index + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const target = results[activeIndex]
      if (target) choose(target.key)
    }
  }

  if (!open) return null

  return (
    <div className="command-palette-overlay" onClick={() => setOpen(false)}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="command-palette"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <input
          ref={inputRef}
          type="text"
          aria-label="Search pages"
          placeholder="Search pages… (e.g. upload dataset, pilot metrics)"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <ul role="listbox" aria-label="Search results">
          {results.length === 0 && <li className="command-palette-empty">No matching pages.</li>}
          {results.map((item, index) => (
            <li key={item.key}>
              <button
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={index === activeIndex ? 'active' : ''}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => choose(item.key)}
              >
                <span>{item.label}</span>
                {item.group && <small>{item.group}</small>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
