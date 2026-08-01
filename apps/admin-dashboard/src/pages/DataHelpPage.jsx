import { useState } from 'react'
import { dataHelpEntries, getHelpEntry } from '../data/helpRegistry.js'

export default function DataHelpPage({ onNavigate }) {
  const [language, setLanguage] = useState('en')
  const [openId, setOpenId] = useState(dataHelpEntries[0]?.pageId ?? null)

  return (
    <section className="help-workspace">
      <header className="section-heading">
        <div>
          <h2>Data — Help &amp; Guide</h2>
          <p>Purpose, prerequisites, workflow, and common blockers for each implemented Data page.</p>
          <p className="notice">The floating Assistant (bottom-right, on every dashboard page) answers the same kind of question live, for any page -- not just Data -- and can also summarize what is currently pending.</p>
        </div>
        <div className="dataset-tabs" role="group" aria-label="Help language">
          <button className={language === 'en' ? 'active' : ''} onClick={() => setLanguage('en')}>English</button>
          <button className={language === 'ta' ? 'active' : ''} onClick={() => setLanguage('ta')}>தமிழ்</button>
        </div>
      </header>
      <div className="help-entries">
        {dataHelpEntries.map((entry) => (
          <article key={entry.pageId} className="help-entry">
            <button
              className="help-entry-toggle"
              aria-expanded={openId === entry.pageId}
              onClick={() => setOpenId((current) => (current === entry.pageId ? null : entry.pageId))}
            >
              <strong>{entry.title[language]}</strong>
              <span>{openId === entry.pageId ? '▾' : '▸'}</span>
            </button>
            {openId === entry.pageId && (
              <div className="help-entry-body">
                <p>{entry.purpose[language]}</p>
                {entry.prerequisites.length > 0 && (
                  <>
                    <h4>{language === 'en' ? 'Prerequisites' : 'தேவையானவை'}</h4>
                    <ul>{entry.prerequisites.map((item, index) => <li key={index}>{item[language]}</li>)}</ul>
                  </>
                )}
                {entry.workflowSteps.length > 0 && (
                  <>
                    <h4>{language === 'en' ? 'Standard workflow' : 'வழக்கமான பணிமுறை'}</h4>
                    <ol>{entry.workflowSteps.map((item, index) => <li key={index}>{item[language]}</li>)}</ol>
                  </>
                )}
                {entry.commonIssues.length > 0 && (
                  <>
                    <h4>{language === 'en' ? 'Common blockers' : 'பொதுவான தடைகள்'}</h4>
                    <ul>{entry.commonIssues.map((item, index) => <li key={index} className="row-warning">{item[language]}</li>)}</ul>
                  </>
                )}
                <p className="row-warning">{entry.safetyNote[language]}</p>
                <div className="help-entry-actions">
                  {entry.activeKey && onNavigate && (
                    <button onClick={() => onNavigate(entry.activeKey)}>
                      {language === 'en' ? `Open ${entry.title.en}` : `${entry.title.ta} திற`}
                    </button>
                  )}
                  {entry.nextPageIds.map((nextId) => {
                    const next = getHelpEntry(nextId)
                    if (!next) return null
                    return (
                      <button key={nextId} className="help-next" onClick={() => setOpenId(nextId)}>
                        {language === 'en' ? `Next: ${next.title.en}` : `அடுத்து: ${next.title.ta}`}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
