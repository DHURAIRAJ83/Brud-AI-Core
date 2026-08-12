// Renders whichever of these real fields a citation actually has --
// {source_name, source_public_id, source_version_public_id, rank, score,
// text_preview} -- all already returned by the real grounded-chat backend
// response today, just rendered inconsistently across the widget (drops
// text_preview/source_version_public_id) and the MB-37 test panel (drops
// nothing). This is a consistent, honest rendering of already-real data.
export default function CitationCard({ citation }) {
  const { source_name, source_public_id, source_version_public_id, rank, score, text_preview } = citation
  const title = source_name || source_public_id

  return (
    <article className="citation-card">
      <header className="citation-card-header">
        <strong>{title}</strong>
        <span className="citation-card-meta">
          {typeof rank === 'number' && `rank ${rank}`}
          {typeof rank === 'number' && typeof score === 'number' && ' · '}
          {typeof score === 'number' && `score ${score.toFixed(2)}`}
        </span>
      </header>
      {text_preview && <p className="citation-card-preview">{text_preview}</p>}
      {source_version_public_id && (
        <small className="citation-card-version">version {source_version_public_id.slice(0, 8)}</small>
      )}
    </article>
  )
}
