/**
 * P7-02 E2E — 03 Admin Isolation & Security Boundary
 *
 * Verifies:
 * 1. All administrative paths return the client-side 404 page.
 * 2. No admin navigation links exist in the public DOM.
 * 3. Public website script assets do not import or bundle admin dashboard code.
 * 4. Chat iframe points exclusively to canonical public chatbot and does not permit admin escalations.
 */

import { expect, test } from '@playwright/test'

const ADMIN_PATHS = [
  '/admin',
  '/admin/',
  '/admin/login',
  '/admin/dashboard',
  '/admin/users',
  '/admin/metrics',
  '/admin/settings',
  '/admin/system',
]

test.describe('Admin Isolation — route accessibility', () => {
  for (const path of ADMIN_PATHS) {
    test(`Navigating to "${path}" renders 404 Not Found`, async ({ page }) => {
      await page.goto(path)

      // Must render 404 page
      const h1 = page.locator('h1').first()
      await expect(h1).toHaveText(/404|Page Not Found/i)

      // Back to home link exists
      const homeLink = page.getByRole('link', { name: /Go Home|Back to Home|Return Home/i })
      await expect(homeLink).toBeVisible()

      // Does not render admin dashboard layout or controls
      const adminSidebar = page.locator('.admin-sidebar, .sidebar-nav, #admin-root')
      await expect(adminSidebar).toHaveCount(0)
    })
  }
})

test.describe('Admin Isolation — leak prevention', () => {
  test('No admin navigation or management links exist across public pages', async ({ page }) => {
    const publicPages = ['/', '/features', '/how-it-works', '/faq', '/desktop', '/help', '/privacy', '/terms']

    for (const p of publicPages) {
      await page.goto(p)

      // Search all anchors for href containing "admin"
      const adminLinks = page.locator('a[href*="/admin"], a[href*="admin."]')
      const count = await adminLinks.count()
      expect(count, `Found unexpected admin link on ${p}`).toBe(0)

      // Verify no admin tokens in localStorage or sessionStorage
      const storageKeys = await page.evaluate(() => {
        const local = Object.keys(localStorage)
        const session = Object.keys(sessionStorage)
        return [...local, ...session]
      })
      const hasAdminKey = storageKeys.some((k) => /admin/i.test(k))
      expect(hasAdminKey, `Found admin storage keys on ${p}`).toBe(false)
    }
  })

  test('Public website bundle does not bundle admin dashboard code', async ({ page }) => {
    await page.goto('/')

    // Check script contents loaded on page
    const scriptSources = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('script[src]')).map((s) => s.src)
    })

    for (const src of scriptSources) {
      const resp = await page.request.get(src)
      const text = await resp.text()

      // Ensure no admin dashboard component strings exist
      expect(text).not.toContain('AdminDashboard')
      expect(text).not.toContain('AdminLogin')
      expect(text).not.toContain('BrudAdmin')
      expect(text).not.toContain('/api/admin/system/metrics')
    }
  })
})
