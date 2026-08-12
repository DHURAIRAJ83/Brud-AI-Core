import { useState } from 'react'
import AdminAssistantWidget from './admin-assistant/AdminAssistantWidget.jsx'
import CommandPalette from './CommandPalette.jsx'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'
import { ThemeProvider } from '../theme/ThemeProvider.jsx'
import { ToastProvider } from './Toast.jsx'

export default function DashboardLayout({ active, onSelect, onOpenMiniBrainAssistant, admin, onLogout, children }) {
  const [open, setOpen] = useState(false)
  return <ThemeProvider><ToastProvider><div className="dashboard"><Sidebar active={active} open={open} onSelect={onSelect} onClose={() => setOpen(false)} /><div className="content"><Topbar title={active} onMenu={() => setOpen(!open)} admin={admin} onLogout={onLogout} /><main>{children}</main></div>{open && <button className="overlay" aria-label="Close menu" onClick={() => setOpen(false)} />}<AdminAssistantWidget active={active} onNavigate={onSelect} onOpenMiniBrainAssistant={onOpenMiniBrainAssistant} admin={admin} /><CommandPalette onSelect={onSelect} /></div></ToastProvider></ThemeProvider>
}
