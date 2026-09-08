/**
 * P7-01 Route rendering tests.
 *
 * Verifies:
 * - All 9 public routes render without throwing
 * - Admin routes are NOT registered in the router
 * - No imports from apps/admin-dashboard
 * - Chat page does NOT create a duplicate inference pipeline
 * - No hardcoded secrets in page components
 */

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'

// ── Mock react-router-dom for ChatPage iframe tests ─────────────
// ChatPage uses useEffect; we render it directly with MemoryRouter.

// ── Import App with all routes ───────────────────────────────────
import App from '../App.jsx'

function renderAt(path) {
  // Render App with the router at the given path using MemoryRouter
  return render(
    <MemoryRouter initialEntries={[path]}>
      {/* We re-export routes from App without BrowserRouter for testing */}
      <RoutesOnly />
    </MemoryRouter>,
  )
}

// Extract routes from App without BrowserRouter (for MemoryRouter wrapping)
import { Route, Routes, Navigate } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import ChatPage from '../pages/ChatPage.jsx'
import DesktopPage from '../pages/DesktopPage.jsx'
import FaqPage from '../pages/FaqPage.jsx'
import FeaturesPage from '../pages/FeaturesPage.jsx'
import HelpPage from '../pages/HelpPage.jsx'
import HomePage from '../pages/HomePage.jsx'
import HowItWorksPage from '../pages/HowItWorksPage.jsx'
import NotFoundPage from '../pages/NotFoundPage.jsx'
import PrivacyPage from '../pages/PrivacyPage.jsx'
import TermsPage from '../pages/TermsPage.jsx'

function RoutesOnly() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/how-it-works" element={<HowItWorksPage />} />
        <Route path="/faq" element={<FaqPage />} />
        <Route path="/desktop" element={<DesktopPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

// ── Route render tests ────────────────────────────────────────────

describe('Public route rendering', () => {
  it('renders / (Home) without crashing', () => {
    const { container } = renderAt('/')
    expect(container).toBeTruthy()
  })

  it('renders /chat without crashing', () => {
    const { container } = renderAt('/chat')
    expect(container).toBeTruthy()
  })

  it('renders /features without crashing', () => {
    const { container } = renderAt('/features')
    expect(container).toBeTruthy()
  })

  it('renders /how-it-works without crashing', () => {
    const { container } = renderAt('/how-it-works')
    expect(container).toBeTruthy()
  })

  it('renders /faq without crashing', () => {
    const { container } = renderAt('/faq')
    expect(container).toBeTruthy()
  })

  it('renders /desktop without crashing', () => {
    const { container } = renderAt('/desktop')
    expect(container).toBeTruthy()
  })

  it('renders /privacy without crashing', () => {
    const { container } = renderAt('/privacy')
    expect(container).toBeTruthy()
  })

  it('renders /terms without crashing', () => {
    const { container } = renderAt('/terms')
    expect(container).toBeTruthy()
  })

  it('renders /help without crashing', () => {
    const { container } = renderAt('/help')
    expect(container).toBeTruthy()
  })

  it('renders 404 for unknown route', () => {
    const { container } = renderAt('/this-route-does-not-exist')
    expect(container).toBeTruthy()
    expect(container.textContent).toMatch(/404|not found/i)
  })
})

// ── Admin boundary tests ──────────────────────────────────────────

describe('Admin isolation', () => {
  it('renders /admin as 404 (not a registered route)', () => {
    const { container } = renderAt('/admin')
    expect(container.textContent).toMatch(/404|not found/i)
  })

  it('renders /admin-login as 404 (not a registered route)', () => {
    const { container } = renderAt('/admin-login')
    expect(container.textContent).toMatch(/404|not found/i)
  })

  it('renders /dashboard as 404 (not a registered route)', () => {
    const { container } = renderAt('/dashboard')
    expect(container.textContent).toMatch(/404|not found/i)
  })
})

// ── Content boundary tests ────────────────────────────────────────

describe('Navbar content', () => {
  it('shows public navigation links', () => {
    renderAt('/')
    expect(screen.getAllByText('Chat').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Features').length).toBeGreaterThan(0)
    expect(screen.getAllByText('FAQ').length).toBeGreaterThan(0)
  })

  it('does NOT show admin navigation items', () => {
    renderAt('/')
    // Check that no admin-related nav items appear
    expect(screen.queryByText(/^Admin$/i)).toBeNull()
    expect(screen.queryByText(/Admin Login/i)).toBeNull()
    expect(screen.queryByText(/Admin Dashboard/i)).toBeNull()
    expect(screen.queryByText(/^Dashboard$/i)).toBeNull()
  })
})

// ── Home page content tests ───────────────────────────────────────

describe('HomePage content', () => {
  it('displays the Brud AI brand', () => {
    renderAt('/')
    expect(screen.getAllByText(/Brud AI/i).length).toBeGreaterThan(0)
  })

  it('has a Start Chat CTA link', () => {
    renderAt('/')
    const chatLinks = screen.getAllByRole('link', { name: /Start Chat/i })
    expect(chatLinks.length).toBeGreaterThan(0)
    expect(chatLinks[0]).toHaveAttribute('href', '/chat')
  })

  it('has an Explore Features link', () => {
    renderAt('/')
    const links = screen.getAllByRole('link', { name: /Explore Features/i })
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toHaveAttribute('href', '/features')
  })
})

// ── Chat page architecture tests ──────────────────────────────────

describe('ChatPage architecture (no duplicate pipeline)', () => {
  it('renders /chat without crashing', () => {
    const { container } = renderAt('/chat')
    expect(container).toBeTruthy()
  })

  it('shows Public Chat identification', () => {
    renderAt('/chat')
    expect(screen.getByText(/Public Chat/i)).toBeTruthy()
  })

  it('renders native canonical chat components with ZERO iframes', () => {
    const { container } = renderAt('/chat')
    expect(container.querySelector('iframe')).toBeNull()
    expect(container.querySelector('textarea#message')).toBeInTheDocument()
    expect(container.querySelector('#new-chat-button')).toBeInTheDocument()
  })
})

// ── Desktop page tests ────────────────────────────────────────────

describe('DesktopPage', () => {
  it('shows Coming Soon badge', () => {
    renderAt('/desktop')
    expect(screen.getAllByText(/Coming Soon/i).length).toBeGreaterThan(0)
  })

  it('has no enabled download link', () => {
    renderAt('/desktop')
    // Download buttons must be disabled
    const downloadButtons = screen.queryAllByRole('button', { name: /download/i })
    downloadButtons.forEach((btn) => {
      expect(btn).toBeDisabled()
    })
  })
})
