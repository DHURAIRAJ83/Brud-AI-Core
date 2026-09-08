/**
 * P7-02 E2E — 02 Responsive: Validates layout at 6 viewport sizes.
 *
 * Viewports tested:
 *   320px  — smallest mobile (iPhone SE narrow)
 *   375px  — standard mobile (iPhone SE)
 *   480px  — large mobile
 *   768px  — tablet
 *  1024px  — laptop
 *  1440px  — desktop
 *
 * Checks:
 * - Page loads without overflow errors
 * - Navbar is present
 * - Footer is present
 * - No horizontal scroll (body width == viewport width)
 * - Mobile hamburger is visible on small screens
 * - Desktop nav links are visible on large screens
 */

import { expect, test } from '@playwright/test'

const VIEWPORTS = [
  { name: '320px mobile',  width: 320,  height: 568 },
  { name: '375px mobile',  width: 375,  height: 812 },
  { name: '480px mobile',  width: 480,  height: 854 },
  { name: '768px tablet',  width: 768,  height: 1024 },
  { name: '1024px laptop', width: 1024, height: 768 },
  { name: '1440px desktop',width: 1440, height: 900 },
]

const ROUTES_TO_CHECK = ['/', '/features', '/how-it-works', '/faq', '/help']

for (const vp of VIEWPORTS) {
  test.describe(`Responsive — ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } })

    for (const route of ROUTES_TO_CHECK) {
      test(`${route} loads without horizontal overflow at ${vp.width}px`, async ({ page }) => {
        await page.goto(route)

        // Navbar present
        const nav = page.locator('nav[aria-label="Main navigation"]')
        await expect(nav).toBeVisible()

        // Footer present
        const footer = page.locator('footer')
        await expect(footer).toBeVisible()

        // No horizontal scroll: scrollWidth should not exceed clientWidth by more than 2px
        const overflow = await page.evaluate(() => {
          return document.body.scrollWidth - document.body.clientWidth
        })
        expect(overflow).toBeLessThanOrEqual(2)
      })
    }

    if (vp.width < 768) {
      test(`${vp.name}: mobile hamburger button is visible`, async ({ page }) => {
        await page.goto('/')
        const hamburger = page.getByRole('button', { name: /Open menu/i })
        await expect(hamburger).toBeVisible()
      })

      test(`${vp.name}: desktop nav link list is hidden on mobile`, async ({ page }) => {
        await page.goto('/')
        // The desktop nav list (.navbar-nav) should not be visible at mobile widths
        const desktopLinks = page.locator('.navbar-nav')
        // Either hidden or not rendered at this viewport
        const isVisible = await desktopLinks.isVisible().catch(() => false)
        // On mobile (<768) the desktop links should be hidden
        expect(isVisible).toBe(false)
      })
    }

    if (vp.width >= 1024) {
      test(`${vp.name}: desktop nav links are visible`, async ({ page }) => {
        await page.goto('/')
        const desktopLinks = page.locator('.navbar-nav')
        await expect(desktopLinks).toBeVisible()
      })
    }
  })
}
