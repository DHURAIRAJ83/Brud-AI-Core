import { useState } from 'react'
import DashboardLayout from './components/DashboardLayout.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import PlaceholderPage from './pages/PlaceholderPage.jsx'

export default function App() {
  const [active, setActive] = useState('Overview')
  return <DashboardLayout active={active} onSelect={setActive}>{active === 'Overview' ? <OverviewPage /> : <PlaceholderPage name={active} />}</DashboardLayout>
}
