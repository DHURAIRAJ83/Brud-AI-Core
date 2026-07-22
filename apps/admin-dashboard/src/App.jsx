import { useState } from 'react'
import DashboardLayout from './components/DashboardLayout.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import PlaceholderPage from './pages/PlaceholderPage.jsx'
import SystemPage from './pages/SystemPage.jsx'

export default function App() {
  const initialPage = decodeURIComponent(window.location.hash.slice(1)) || 'Overview'
  const [active, setActive] = useState(initialPage)
  const selectPage = (page) => {
    window.history.replaceState(null, '', `#${encodeURIComponent(page)}`)
    setActive(page)
  }
  let page = <PlaceholderPage name={active} />
  if (active === 'Overview') page = <OverviewPage />
  if (active === 'System') page = <SystemPage />
  return <DashboardLayout active={active} onSelect={selectPage}>{page}</DashboardLayout>
}
