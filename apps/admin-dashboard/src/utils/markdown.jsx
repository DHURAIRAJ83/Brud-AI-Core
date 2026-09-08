// Enhanced hand-rolled markdown formatter for Brud AI Admin Assistant
// Supports: bold (**text**), inline code (`code`), fenced code blocks (```lang ... ```),
// markdown tables (| a | b |), bullet lists (- item), and line breaks.
// Zero external runtime dependencies.

export function formatMessageText(text) {
  if (!text) return null

  const raw = String(text)

  // If text contains fenced code blocks, split and handle code blocks
  if (raw.includes('```')) {
    const segments = raw.split(/(```[\s\S]*?```)/g)
    return segments.map((segment, segIdx) => {
      if (segment.startsWith('```') && segment.endsWith('```')) {
        const withoutTicks = segment.slice(3, -3)
        const newlinePos = withoutTicks.indexOf('\n')
        let language = ''
        let codeContent = withoutTicks
        if (newlinePos !== -1) {
          language = withoutTicks.slice(0, newlinePos).trim()
          codeContent = withoutTicks.slice(newlinePos + 1)
        }
        return (
          <div key={`codeblock-${segIdx}`} className="chat-code-block" style={{ margin: '0.5rem 0', borderRadius: '8px', overflow: 'hidden', background: '#0a0f1d', border: '1px solid #1e293b' }}>
            {language && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 10px', background: '#111827', fontSize: '0.7rem', color: '#94a3b8', borderBottom: '1px solid #1e293b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <span>{language}</span>
              </div>
            )}
            <pre style={{ margin: 0, padding: '10px 12px', overflowX: 'auto', fontSize: '0.8rem', fontFamily: 'monospace', color: '#e2e8f0', lineHeight: 1.45 }}>
              <code>{codeContent}</code>
            </pre>
          </div>
        )
      }
      return <span key={`text-${segIdx}`}>{renderInlineMarkdown(segment)}</span>
    })
  }

  return renderInlineMarkdown(raw)
}

function renderInlineMarkdown(content) {
  const lines = content.split('\n')
  const elements = []
  let tableRows = []
  let inTable = false

  function flushTable(tableIndex) {
    if (tableRows.length === 0) return
    const headerRow = tableRows[0]
    const dataRows = tableRows.slice(1).filter((r) => !r.every((c) => /^[-:| ]+$/.test(c)))

    elements.push(
      <div key={`table-wrapper-${tableIndex}`} style={{ margin: '0.5rem 0', overflowX: 'auto' }}>
        <table className="chat-markdown-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', border: '1px solid #334155' }}>
          <thead>
            <tr style={{ background: '#1e293b', borderBottom: '1px solid #334155' }}>
              {headerRow.map((cell, cIdx) => (
                <th key={cIdx} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: '#38bdf8' }}>
                  {formatInlineFormatting(cell)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, rIdx) => (
              <tr key={rIdx} style={{ borderBottom: '1px solid #1e293b', background: rIdx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                {row.map((cell, cIdx) => (
                  <td key={cIdx} style={{ padding: '6px 10px', color: '#e2e8f0' }}>
                    {formatInlineFormatting(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
    tableRows = []
    inTable = false
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // Check for table line
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.includes('|')) {
      const cells = trimmed.slice(1, -1).split('|').map((c) => c.trim())
      tableRows.push(cells)
      inTable = true
      continue
    } else if (inTable) {
      flushTable(i)
    }

    // Check for headings
    if (trimmed.startsWith('### ')) {
      elements.push(
        <div key={`h3-${i}`} style={{ fontWeight: 700, fontSize: '0.88rem', color: '#38bdf8', marginTop: '0.4rem', marginBottom: '0.2rem' }}>
          {formatInlineFormatting(trimmed.slice(4))}
        </div>
      )
      continue
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <div key={`h2-${i}`} style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f8fafc', marginTop: '0.5rem', marginBottom: '0.25rem' }}>
          {formatInlineFormatting(trimmed.slice(3))}
        </div>
      )
      continue
    }
    if (trimmed.startsWith('# ')) {
      elements.push(
        <div key={`h1-${i}`} style={{ fontWeight: 800, fontSize: '0.98rem', color: '#f8fafc', marginTop: '0.6rem', marginBottom: '0.3rem' }}>
          {formatInlineFormatting(trimmed.slice(2))}
        </div>
      )
      continue
    }

    // Check for bullet lists
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <div key={`li-${i}`} style={{ display: 'flex', gap: '0.4rem', marginLeft: '0.5rem', margin: '2px 0' }}>
          <span style={{ color: '#38bdf8' }}>•</span>
          <span>{formatInlineFormatting(trimmed.slice(2))}</span>
        </div>
      )
      continue
    }

    // Regular line with inline formatting
    elements.push(
      <span key={`line-${i}`}>
        {formatInlineFormatting(line)}
        {i < lines.length - 1 && <br />}
      </span>
    )
  }

  if (inTable) {
    flushTable(lines.length)
  }

  return elements
}

function formatInlineFormatting(text) {
  if (!text) return text
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} style={{ fontWeight: 700, color: '#fff' }}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={index}
          style={{
            background: '#1e293b',
            color: '#38bdf8',
            padding: '1px 5px',
            borderRadius: '4px',
            fontSize: '0.82em',
            fontFamily: 'monospace',
            border: '1px solid #334155',
          }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}
