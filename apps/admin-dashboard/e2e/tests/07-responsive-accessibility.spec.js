import { expect, openSidebarPage, test } from '../fixtures.js'

const MOBILE_VIEWPORT = { width: 390, height: 844 } // iPhone 12-class

function tabButton(page, name) {
  return page
    .getByRole('navigation', { name: 'Production readiness sections' })
    .getByRole('button', { name, exact: true })
}

async function hasNoHorizontalOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
}

test.describe('Mobile layout', () => {
  test('the sidebar is off-canvas by default and opens/closes via the menu button', async ({
    authenticatedPage: page,
  }) => {
    await page.setViewportSize(MOBILE_VIEWPORT)
    const sidebar = page.locator('aside.sidebar')
    await expect(sidebar).not.toHaveClass(/open/)

    await page.getByRole('button', { name: 'Open menu' }).click()
    await expect(sidebar).toHaveClass(/open/)

    // Choosing a page both navigates and auto-closes the mobile menu --
    // real behavior already implemented in Sidebar.jsx's choose(), not
    // something this test invents.
    await openSidebarPage(page, 'Production Readiness')
    await expect(page.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()
    await expect(sidebar).not.toHaveClass(/open/)
  })

  test('the overlay closes the menu without navigating away', async ({ authenticatedPage: page }) => {
    await page.setViewportSize(MOBILE_VIEWPORT)
    const sidebar = page.locator('aside.sidebar')
    await page.getByRole('button', { name: 'Open menu' }).click()
    await expect(sidebar).toHaveClass(/open/)

    // The overlay sits below the drawer in stacking order (z-index 2 vs
    // 3), so it is only clickable in the region the drawer doesn't cover
    // -- the same as any real finger tap on the dimmed backdrop next to
    // an open mobile drawer. Click near the right edge, outside the
    // drawer's 250px width, rather than the element's default center.
    await page.getByRole('button', { name: 'Close menu' }).click({ position: { x: 350, y: 400 } })
    await expect(sidebar).not.toHaveClass(/open/)
    await expect(page.getByRole('heading', { name: 'Overview', level: 1 })).toBeVisible()
  })

  test('no horizontal scroll on the Overview page at mobile width', async ({ authenticatedPage: page }) => {
    await page.setViewportSize(MOBILE_VIEWPORT)
    expect(await hasNoHorizontalOverflow(page)).toBe(true)
  })

  test('no horizontal scroll on the Production Readiness page (widest data tables) at mobile width', async ({
    authenticatedPage: page,
  }) => {
    await page.setViewportSize(MOBILE_VIEWPORT)
    await page.getByRole('button', { name: 'Open menu' }).click()
    await openSidebarPage(page, 'Production Readiness')
    await expect(page.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()

    for (const tab of ['Model Release', 'Canary & Activation', 'Regression']) {
      await tabButton(page, tab).click()
      expect(await hasNoHorizontalOverflow(page)).toBe(true)
    }
  })
})

test.describe('Accessibility basics', () => {
  test('the page exposes one banner, one main, and named navigation landmarks', async ({
    authenticatedPage: page,
  }) => {
    await expect(page.getByRole('banner')).toHaveCount(1)
    await expect(page.getByRole('main')).toHaveCount(1)
    await expect(page.getByRole('navigation', { name: 'Admin modules' })).toBeVisible()
  })

  test('exactly one h1 is present and it reflects the active page', async ({ authenticatedPage: page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1)
    await expect(page.getByRole('heading', { name: 'Overview', level: 1 })).toBeVisible()

    await openSidebarPage(page, 'Production Readiness')
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1)
    await expect(page.getByRole('heading', { name: 'Production Readiness', level: 1 })).toBeVisible()
  })

  test('every sidebar nav button has a non-empty accessible name', async ({ authenticatedPage: page }) => {
    const buttons = await page
      .getByRole('navigation', { name: 'Admin modules' })
      .getByRole('button')
      .all()
    expect(buttons.length).toBeGreaterThan(0)
    for (const button of buttons) {
      const name = await button.evaluate((el) => el.getAttribute('aria-label') || el.textContent.trim())
      expect(name.length).toBeGreaterThan(0)
    }
  })

  test('login form fields are reachable by their accessible label, not just placeholder text', async ({
    page,
  }) => {
    await page.goto('/')
    await expect(page.getByLabel('Username')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
  })

  test('the mobile menu button has a real accessible name once visible (mobile width)', async ({
    authenticatedPage: page,
  }) => {
    // The button is `display: none` above the 800px breakpoint (see
    // index.css) and correctly absent from the accessibility tree at
    // desktop width -- a hidden, non-functional control isn't something
    // assistive tech should announce. At mobile width, where it is a
    // real, usable control, it must expose a real name, not an empty or
    // placeholder label.
    await page.setViewportSize(MOBILE_VIEWPORT)
    const name = await page.getByRole('button', { name: 'Open menu' }).evaluate((el) => el.getAttribute('aria-label'))
    expect(name).toBe('Open menu')
  })
})
