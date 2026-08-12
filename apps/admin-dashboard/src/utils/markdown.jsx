// Generalized from MiniBrainPage.jsx's `lrFormatMessageText` (the only
// markdown renderer anywhere in this frontend) so Phase 3's chat
// components can reuse it. MiniBrainPage.jsx itself is left untouched --
// it keeps its own inline copy; only new surfaces import this one.
//
// Minimal hand-rolled markdown: **bold**, `code`, and newlines only -- no
// markdown library exists anywhere in this frontend today.
export function formatMessageText(text) {
  const parts = String(text || '').split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>
    return part.split('\n').map((line, lineIndex, arr) => (
      <span key={`${index}-${lineIndex}`}>{line}{lineIndex < arr.length - 1 && <br />}</span>
    ))
  })
}
