import { useState } from 'react'
import MiniBrainChatTab from './assistant-center/MiniBrainChatTab.jsx'
import PublicChatMonitorTab from './assistant-center/PublicChatMonitorTab.jsx'

const TABS = ['Admin Tasks', 'Mini Brain Chat', 'Public Chat Monitor']

const NOTICE = 'A single entry point across three real, separate systems: the governed Admin Assistant workflow, Mini Brain’s real chat/grounded-chat runtime, and Public Chat monitoring. Each tab reuses the exact same APIs those systems already use elsewhere -- nothing here is a new backend surface.'

export default function AssistantCenterPage({ admin, onNavigate }) {
  const [tab, setTab] = useState('Admin Tasks')

  return (
    <>
      <section className="system-heading">
        <span>Assistant Center</span>
        <h2>Assistant Center</h2>
        <p>{NOTICE}</p>
      </section>

      <nav className="dataset-tabs" aria-label="Assistant Center sections">
        {TABS.map((item) => (
          <button
            key={item}
            type="button"
            className={tab === item ? 'active' : ''}
            aria-current={tab === item ? 'page' : undefined}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </nav>

      {tab === 'Admin Tasks' && (
        <section className="assistant-center-admin-tasks">
          <p className="notice">
            The governed Admin Assistant workflow (Guidance, Propose an Action, Proposals &amp; Admin
            Review) keeps its own dedicated page as the single place it is mounted -- Assistant
            Center links out to it instead of mounting a second copy here.
          </p>
          <button type="button" onClick={() => onNavigate?.('Admin Assistant')}>
            Open Admin Assistant
          </button>
        </section>
      )}
      {tab === 'Mini Brain Chat' && <MiniBrainChatTab admin={admin} />}
      {tab === 'Public Chat Monitor' && <PublicChatMonitorTab />}
    </>
  )
}
