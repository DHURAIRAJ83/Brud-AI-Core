import { useState } from 'react'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'

export default function DashboardLayout({ active, onSelect, admin, onLogout, children }) {
  const [open, setOpen] = useState(false)
  return <div className="dashboard"><Sidebar active={active} open={open} onSelect={onSelect} onClose={() => setOpen(false)} /><div className="content"><Topbar title={active} onMenu={() => setOpen(!open)} admin={admin} onLogout={onLogout} /><main>{children}</main></div>{open && <button className="overlay" aria-label="Close menu" onClick={() => setOpen(false)} />}</div>
}
