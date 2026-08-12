import { expect, openSidebarPage, test } from '../fixtures.js'

// Real, reproduced evidence behind this file (Phase 15A Step 13, per
// docs/production/phase15a_production_verification_plan.md §9):
//
// - Top-level page selection (App.jsx) IS hash-encoded and DOES survive a
//   hard refresh -- `useState`'s initializer reads `window.location.hash`
//   once at mount, which is exactly what a hard refresh re-triggers.
// - What was NOT hash-encoded before this fix: which sub-tab of
//   ProductionReadinessPage is active. A hard refresh on, say, "Model
//   Release" silently dropped back to "Overview". Fixed by encoding
//   `?tab=<name>` into the same hash fragment.
// - A same-document, hash-only `page.goto()` (no reload) does NOT trigger
//   React to re-render with the new page, because there is no
//   `hashchange` listener -- this is a separate, narrower, and
//   deliberately out-of-scope limitation (see the plan doc); it only
//   matters for same-document navigation, which real users never trigger
//   this way (they either click the sidebar or reload/open a bookmarked
//   URL). This file always exercises the *reload* path, which is the only
//   path production deep-linking actually relies on.

function tabButton(page, name) {
  return page
    .getByRole('navigation', { name: 'Production readiness sections' })
    .getByRole('button', { name, exact: true })
}

test.describe('Hash deep-linking', () => {
  test('a hard reload preserves both the top-level page and the active sub-tab', async ({
    authenticatedPage: page,
  }) => {
    await openSidebarPage(page, 'Production Readiness')
    await expect(page.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()

    await tabButton(page, 'Model Release').click()
    await expect(tabButton(page, 'Model Release')).toHaveClass(/active/)
    await expect(page).toHaveURL(/#Production%20Readiness\?tab=Model\+Release/)

    await page.reload()

    await expect(page.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()
    await expect(tabButton(page, 'Model Release')).toHaveClass(/active/)
  })

  test('opening a bookmarked deep-link URL directly lands on the right page and tab', async ({
    authenticatedPage: page,
  }) => {
    // A `goto()` on the *same* page object that's already loaded the app
    // is a same-document, hash-only jump (no React re-render -- this is
    // the documented, out-of-scope limitation). To genuinely simulate a
    // bookmarked URL opened fresh, navigate a brand-new page (its very
    // first navigation ever, so the browser performs a real full load)
    // that shares the already-authenticated context's session cookie.
    const freshPage = await page.context().newPage()
    await freshPage.goto('/#Production Readiness?tab=Regression')

    await expect(freshPage.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()
    await expect(tabButton(freshPage, 'Regression')).toHaveClass(/active/)
    await freshPage.close()
  })

  test('an unrecognized tab in the URL falls back to Overview honestly, not a crash', async ({
    authenticatedPage: page,
  }) => {
    const freshPage = await page.context().newPage()
    await freshPage.goto('/#Production Readiness?tab=Nonexistent')

    await expect(freshPage.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()
    await expect(tabButton(freshPage, 'Overview')).toHaveClass(/active/)
    await freshPage.close()
  })
})
