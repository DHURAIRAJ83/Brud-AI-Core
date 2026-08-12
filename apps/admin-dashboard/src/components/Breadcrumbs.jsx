import { navTree } from './Sidebar.jsx'

// Pure derivation over navTree + the active page key -- no App.jsx changes
// needed, since `active` and navTree are already threaded to wherever this
// is rendered.
export function findBreadcrumb(tree, active) {
  for (const item of tree) {
    if (!item.group && item.key === active) return [item.label]
    if (item.group) {
      const child = item.children.find((candidate) => candidate.key === active)
      if (child) return [item.label, child.ariaLabel ?? child.label]
    }
  }
  return [active]
}

export default function Breadcrumbs({ active }) {
  const crumbs = findBreadcrumb(navTree, active)
  return (
    <nav aria-label="Breadcrumb" className="breadcrumbs">
      {crumbs.map((crumb, index) => (
        <span key={crumb}>
          {index > 0 && <span className="breadcrumb-separator" aria-hidden="true">›</span>}
          {crumb}
        </span>
      ))}
    </nav>
  )
}
