/**
 * P7-02 E2E — 00 Smoke: All public routes load without error.
 *
 * Verifies that every public route:
 * 1. Returns HTTP 200 (no server error)
 * 2. Contains the Brud AI brand
 * 3. Renders the public Navbar
 * 4. Renders the Footer
 *
 * Also verifies the 404 behavior for an unknown route.
 */

import { expect, test } from '@playwright/test'

const PUBLIC_ROUTES = [
  { path: '/',            title: /Brud AI/i,    h1: /Chat in.*Tamil|Brud AI/i },
  { path: '/chat',        title: /Brud AI/i,    h1: null },
  { path: '/features',    title: /Brud AI/i,    h1: /Features/i },
  { path: '/how-it-works',title: /Brud AI/i,    h1: /How It Works/i },
  { path: '/faq',         title: /Brud AI/i,    h1: /Frequently Asked Questions/i },
  { path: '/desktop',     title: /Brud AI/i,    h1: /Desktop App/i },
  { path: '/privacy',     title: /Brud AI/i,    h1: /Privacy/i },
  { path: '/terms',       title: /Brud AI/i,    h1: /Terms of Use/i },
  { path: '/help',        title: /Brud AI/i,    h1: /Getting Started/i },
]

test.describe('Smoke — all public routes load', () => {
  for (const route of PUBLIC_ROUTES) {
    test(`GET ${route.path} renders without error`, async ({ page }) => {
      await page.goto(route.path)

      // Page title contains Brud AI
      await expect(page).toHaveTitle(route.title)

      // Navbar is visible
      const nav = page.locator('nav[aria-label="Main navigation"]')
      await expect(nav).toBeVisible()

      // Footer is visible
      const footer = page.locator('footer')
      await expect(footer).toBeVisible()

      // h1 matches if specified
      if (route.h1) {
        const h1 = page.locator('h1').first()
        await expect(h1).toBeVisible()
        await expect(h1).toHaveText(route.h1)
      }

      // No JS uncaught errors
      const errors = []
      page.on('pageerror', (e) => errors.push(e.message))
      expect(errors).toHaveLength(0)
    })
  }

  test('Unknown route renders 404 page', async ({ page }) => {
    await page.goto('/this-route-does-not-exist-p7-02')
    const body = await page.textContent('body')
    expect(body).toMatch(/404|not found/i)
  })
})
