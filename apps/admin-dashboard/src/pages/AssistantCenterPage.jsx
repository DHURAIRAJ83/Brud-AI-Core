import { useState } from 'react'
import AdminAssistantPage from './AdminAssistantPage.jsx'
import MiniBrainChatTab from './assistant-center/MiniBrainChatTab.jsx'
import PublicChatMonitorTab from './assistant-center/PublicChatMonitorTab.jsx'

const TABS = ['Admin Tasks', 'Mini Brain Chat', 'Public Chat Monitor']

const NOTICE = 'A single entry point across three real, separate systems: the governed Admin Assistant workflow, Mini Brain’s real chat/grounded-chat runtime, and Public Chat monitoring. Each tab reuses the exact same APIs those systems already use elsewhere -- nothing here is a new backend surface.'

export default function AssistantCenterPage({ admin }) {
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

      {tab === 'Admin Tasks' && <AdminAssistantPage />}
      {tab === 'Mini Brain Chat' && <MiniBrainChatTab admin={admin} />}
      {tab === 'Public Chat Monitor' && <PublicChatMonitorTab />}
    </>
  )
}
