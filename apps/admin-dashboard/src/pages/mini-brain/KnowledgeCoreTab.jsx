import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const knowledgeSubTabs = ['Domains', 'Search', 'Validation', 'Coverage']

export default function KnowledgeCoreTab({
  knowledgeSubTab, selectKnowledgeSubTab,
  kcDomains, seedKnowledge,
  kcQuery, setKcQuery, runKnowledgeSearch, kcResults, openKnowledgeItem, kcSelectedItem,
  runValidation, kcValidation,
  kcCoverage,
}) {
  return (
    <>
      <p className="notice">
        MB-02 -- a structured, keyword-searchable knowledge catalog. No embeddings, no vector
        database, no semantic search: every lookup here is a plain field match.
      </p>
      <div className="dataset-tabs">
        {knowledgeSubTabs.map((value) => (
          <Button key={value} className={knowledgeSubTab === value ? 'active' : ''} onClick={() => selectKnowledgeSubTab(value)}>{value}</Button>
        ))}
      </div>

      {knowledgeSubTab === 'Domains' && (
        <>
          {kcDomains.length === 0 && (
            <div className="form-row"><Button onClick={seedKnowledge}>Seed default knowledge</Button></div>
          )}
          <section className="metric-grid">
            {kcDomains.map((domain) => (
              <StatusCard key={domain.public_id} label={domain.name} value={`${domain.item_count} items`} tone="neutral" />
            ))}
          </section>
        </>
      )}

      {knowledgeSubTab === 'Search' && (
        <>
          <form className="inline-form training-form" onSubmit={runKnowledgeSearch}>
            <label>Search<input value={kcQuery} onChange={(e) => setKcQuery(e.target.value)} placeholder="title, keyword, API, service..." /></label>
            <Button type="submit">Search</Button>
          </form>
          <div className="data-list">
            {kcResults.map((item) => (
              <article key={item.public_id} onClick={() => openKnowledgeItem(item.public_id)} style={{ cursor: 'pointer' }}>
                <strong>{item.title}</strong> — {item.category}
                <div><small>{item.description}</small></div>
              </article>
            ))}
          </div>
          {kcSelectedItem && (
            <div className="notice">
              <h4>{kcSelectedItem.title}</h4>
              <p>{kcSelectedItem.description}</p>
              <p><small>Source: {kcSelectedItem.source} · Version: {kcSelectedItem.version} · Status: {kcSelectedItem.status}</small></p>
              <p>Tags: {kcSelectedItem.tags?.join(', ') || '--'}</p>
              <h5>Relationships</h5>
              <ul>
                {kcSelectedItem.relationships?.map((rel) => (
                  <li key={rel.public_id}>{rel.direction === 'outgoing' ? '→' : '←'} {rel.relationship_type} {rel.related_item_title}</li>
                ))}
                {!kcSelectedItem.relationships?.length && <li>No relationships recorded.</li>}
              </ul>
            </div>
          )}
        </>
      )}

      {knowledgeSubTab === 'Validation' && (
        <>
          <div className="form-row"><Button onClick={runValidation}>Run validation</Button></div>
          {kcValidation && (
            <>
              <section className="metric-grid">
                {Object.entries(kcValidation.summary).map(([type, count]) => (
                  <StatusCard key={type} label={type} value={count} tone={count ? 'waiting' : 'good'} />
                ))}
                {Object.keys(kcValidation.summary).length === 0 && (
                  <StatusCard label="issues" value={0} tone="good" />
                )}
              </section>
              <p className="notice">{kcValidation.issue_count} total issue(s). Duplicate/missing-category/broken-reference/invalid-version checks are structural only -- no semantic judgement is made.</p>
            </>
          )}
        </>
      )}

      {knowledgeSubTab === 'Coverage' && kcCoverage && (
        <>
          <section className="metric-grid">
            <StatusCard label="Total items" value={kcCoverage.overall.total_items} tone="neutral" />
            <StatusCard label="Documentation coverage" value={`${kcCoverage.overall.documentation_coverage_pct ?? 0}%`} tone="neutral" />
            <StatusCard label="Catalog coverage" value={kcCoverage.overall.catalog_coverage_pct != null ? `${kcCoverage.overall.catalog_coverage_pct}%` : 'unknown'} tone="neutral" />
          </section>
          <table>
            <thead><tr><th>Domain</th><th>Items</th><th>Documented</th><th>Doc coverage</th><th>Catalog coverage</th></tr></thead>
            <tbody>
              {kcCoverage.domains.map((d) => (
                <tr key={d.domain}>
                  <td>{d.domain}</td><td>{d.item_count}</td><td>{d.documented_count}</td>
                  <td>{d.documentation_coverage_pct ?? 0}%</td>
                  <td>{d.catalog_coverage_pct != null ? `${d.catalog_coverage_pct}%` : 'unknown'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  )
}
