/**
 * P7-02 E2E — 01 Navigation: Navbar, Footer, CTA, back/forward.
 *
 * Verifies:
 * - All Navbar links navigate to the correct route
 * - Footer links work
 * - CTA "Start Chat" links navigate to /chat
 * - Browser back/forward navigation works
 * - Mobile menu opens and closes
 * - Mobile menu nav links work
 */

import { expect, test } from '@playwright/test'

test.describe('Navigation — desktop navbar', () => {
  test('Navbar contains all required public links', async ({ page }) => {
    await page.goto('/')
    const nav = page.locator('nav[aria-label="Main navigation"]')

    // All nav items must be present
    await expect(nav.getByRole('link', { name: 'Home', exact: true })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Chat' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Features' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'How It Works' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'FAQ' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Desktop' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Help' })).toBeVisible()
  })

  test('Navbar does NOT contain admin links', async ({ page }) => {
    await page.goto('/')
    const nav = page.locator('nav[aria-label="Main navigation"]')
    // These must be absent
    await expect(nav.getByRole('link', { name: /^Admin$/i })).toHaveCount(0)
    await expect(nav.getByRole('link', { name: /Admin Login/i })).toHaveCount(0)
    await expect(nav.getByRole('link', { name: /Admin Dashboard/i })).toHaveCount(0)
    await expect(nav.getByRole('link', { name: /^Dashboard$/i })).toHaveCount(0)
  })

  const NAV_TESTS = [
    { label: 'Chat',          expectedPath: '/chat' },
    { label: 'Features',      expectedPath: '/features' },
    { label: 'How It Works',  expectedPath: '/how-it-works' },
    { label: 'FAQ',           expectedPath: '/faq' },
    { label: 'Desktop',       expectedPath: '/desktop' },
    { label: 'Help',          expectedPath: '/help' },
  ]

  for (const { label, expectedPath } of NAV_TESTS) {
    test(`Navbar "${label}" link navigates to ${expectedPath}`, async ({ page }) => {
      await page.goto('/')
      const nav = page.locator('nav[aria-label="Main navigation"]')
      // Click the first matching nav link (not mobile panel)
      await nav.getByRole('link', { name: label }).first().click()
      await page.waitForURL(`**${expectedPath}`)
      expect(page.url()).toContain(expectedPath)
    })
  }

  test('Home link in navbar returns to /', async ({ page }) => {
    await page.goto('/features')
    const nav = page.locator('nav[aria-label="Main navigation"]')
    await nav.getByRole('link', { name: 'Home', exact: true }).click()
    await page.waitForURL('**/')
    expect(page.url()).toMatch(/\/$|127\.0\.0\.1:\d+$/)
  })
})

test.describe('Navigation — Footer links', () => {
  const FOOTER_LINKS = [
    { label: 'Chat',                    expectedPath: '/chat' },
    { label: 'Features',                expectedPath: '/features' },
    { label: 'How It Works',            expectedPath: '/how-it-works' },
    { label: 'Desktop App',             expectedPath: '/desktop' },
    { label: 'Help / Getting Started',  expectedPath: '/help' },
    { label: 'FAQ',                     expectedPath: '/faq' },
    { label: 'Privacy',                 expectedPath: '/privacy' },
    { label: 'Terms of Use',            expectedPath: '/terms' },
  ]

  for (const { label, expectedPath } of FOOTER_LINKS) {
    test(`Footer "${label}" navigates to ${expectedPath}`, async ({ page }) => {
      await page.goto('/')
      const footer = page.locator('footer')
      await footer.getByRole('link', { name: label }).first().click()
      await page.waitForURL(`**${expectedPath}`)
      expect(page.url()).toContain(expectedPath)
    })
  }
})

test.describe('Navigation — CTA links', () => {
  test('Hero "Start Chat" CTA navigates to /chat', async ({ page }) => {
    await page.goto('/')
    // The hero section has id="hero-start-chat"
    await page.locator('#hero-start-chat').click()
    await page.waitForURL('**/chat')
    expect(page.url()).toContain('/chat')
  })

  test('Hero "Explore Features" CTA navigates to /features', async ({ page }) => {
    await page.goto('/')
    await page.locator('#hero-explore-features').click()
    await page.waitForURL('**/features')
    expect(page.url()).toContain('/features')
  })

  test('Primary CTA "Start Chat" navigates to /chat', async ({ page }) => {
    await page.goto('/')
    await page.locator('#cta-start-chat').click()
    await page.waitForURL('**/chat')
    expect(page.url()).toContain('/chat')
  })
})

test.describe('Navigation — Browser history', () => {
  test('Back/forward navigation works between pages', async ({ page }) => {
    await page.goto('/')
    await page.goto('/features')
    await page.goto('/faq')

    // Go back
    await page.goBack()
    await page.waitForURL('**/features')
    expect(page.url()).toContain('/features')

    // Go back again
    await page.goBack()
    await page.waitForURL('**/')
    expect(page.url()).toMatch(/\/$|127\.0\.0\.1:\d+$/)

    // Go forward
    await page.goForward()
    await page.waitForURL('**/features')
    expect(page.url()).toContain('/features')
  })
})

test.describe('Navigation — Mobile menu', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('Mobile menu opens and closes', async ({ page }) => {
    await page.goto('/')

    const toggle = page.getByRole('button', { name: /Open menu/i })
    await expect(toggle).toBeVisible()

    // Open
    await toggle.click()
    const mobileMenu = page.locator('#mobile-menu')
    await expect(mobileMenu).toBeVisible()

    // Close
    const closeBtn = page.getByRole('button', { name: /Close menu/i })
    await closeBtn.click()
    await expect(mobileMenu).not.toBeVisible()
  })

  test('Mobile menu "Start Chat" navigates to /chat', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Open menu/i }).click()
    const mobileMenu = page.locator('#mobile-menu')
    await expect(mobileMenu).toBeVisible()
    await mobileMenu.getByRole('link', { name: 'Start Chat' }).click()
    await page.waitForURL('**/chat')
    expect(page.url()).toContain('/chat')
  })
})
