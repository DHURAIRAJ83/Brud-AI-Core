import { useEffect, useState } from 'react'
import DashboardLayout from './components/DashboardLayout.jsx'
import DatasetsPage from './pages/DatasetsPage.jsx'
import DocumentsPage from './pages/DocumentsPage.jsx'
import CoreModelPage from './pages/CoreModelPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import PlaceholderPage from './pages/PlaceholderPage.jsx'
import SystemPage from './pages/SystemPage.jsx'
import TokenizerPage from './pages/TokenizerPage.jsx'
import { getMe, login, logout } from './services/api.js'

export default function App() {
  const [auth, setAuth] = useState({ checking: true, admin: null })
  const initialPage = decodeURIComponent(window.location.hash.slice(1)) || 'Overview'
  const [active, setActive] = useState(initialPage)
  useEffect(() => { getMe().then((data) => setAuth({ checking: false, admin: data.admin })).catch(() => setAuth({ checking: false, admin: null })) }, [])
  async function signIn(username, password) { const data = await login(username, password); setAuth({ checking: false, admin: data.admin }); setActive('Overview') }
  async function signOut() { try { await logout() } finally { setAuth({ checking: false, admin: null }); window.history.replaceState(null, '', '#Login') } }
  if (auth.checking) return <main className="login-shell"><div className="notice">Checking admin session…</div></main>
  if (!auth.admin) return <LoginPage onLogin={signIn} />
  const selectPage = (page) => { window.history.replaceState(null, '', `#${encodeURIComponent(page)}`); setActive(page) }
  let page = <PlaceholderPage name={active} />
  if (active === 'Overview') page = <OverviewPage />
  if (active === 'System') page = <SystemPage />
  if (active === 'Datasets') page = <DatasetsPage />
  if (active === 'Documents') page = <DocumentsPage />
  if (active === 'Tokenizer') page = <TokenizerPage />
  if (active === 'Core Model') page = <CoreModelPage />
  return <DashboardLayout active={active} onSelect={selectPage} admin={auth.admin} onLogout={signOut}>{page}</DashboardLayout>
}
