import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import ChatPage from './pages/ChatPage.jsx'
import DesktopPage from './pages/DesktopPage.jsx'
import FaqPage from './pages/FaqPage.jsx'
import FeaturesPage from './pages/FeaturesPage.jsx'
import HelpPage from './pages/HelpPage.jsx'
import HomePage from './pages/HomePage.jsx'
import HowItWorksPage from './pages/HowItWorksPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'

// ARCHITECTURE NOTE (P7-01):
// This is the PUBLIC website application (apps/website/).
// It does NOT import from apps/admin-dashboard/.
// Admin functionality is ONLY accessible through apps/admin-dashboard/ at its own origin.
// The backend enforces all admin authorization — hiding UI is not a security boundary.
//
// Public routes registered here: /, /chat, /features, /how-it-works, /faq,
//   /desktop, /privacy, /terms, /help
//
// Admin routes (/admin, /admin-login, /dashboard) are NOT registered here.

export default function App() {
  return (
    <BrowserRouter>
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
          {/* Unknown routes → controlled 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
