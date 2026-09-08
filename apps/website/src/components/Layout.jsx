import { Outlet, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Footer from './Footer.jsx'
import Navbar from './Navbar.jsx'

// Scroll to top on route change
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }) }, [pathname])
  return null
}

export default function Layout() {
  return (
    <>
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <ScrollToTop />
      <Navbar />
      <main id="main-content" tabIndex={-1} style={{ minHeight: 'calc(100vh - var(--nav-height))' }}>
        <Outlet />
      </main>
      <Footer />
    </>
  )
}
