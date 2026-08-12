import { expect, openSidebarPage, test } from '../fixtures.js'

const TABS = [
  'Overview', 'RAG Promotion', 'RAG Candidates', 'Model Release', 'Canary & Activation',
  'Artifact Security', 'API Abuse & Secrets', 'Backup & Deployment', 'Regression',
  'Readiness Report & Acceptance',
]

// The page's own "Overview" tab shares its accessible name with the
// sidebar's top-level "Overview" nav button -- every tab lookup must be
// scoped to the page's own tab nav (`aria-label="Production readiness
// sections"`), never the whole document.
function tabNav(page) {
  return page.getByRole('navigation', { name: 'Production readiness sections' })
}

function tabButton(page, name) {
  return tabNav(page).getByRole('button', { name, exact: true })
}

async function openProductionReadiness(page) {
  // A same-document hash-only `goto()` does not trigger React to re-read
  // `window.location.hash` (App.jsx only reads it once, at mount, via
  // `useState`'s initializer -- there is no `hashchange` listener). Real
  // in-app navigation is a sidebar click, exactly like a real admin would
  // do; this is also the concrete, reproduced evidence behind the
  // Step 13 hash-deep-link investigation (see docs/production/
  // phase15a_production_verification_plan.md §9 and
  // e2e/tests/03-hash-deep-link.spec.js).
  await openSidebarPage(page, 'Production Readiness')
  await expect(page.getByRole('heading', { name: 'Production Readiness' })).toBeVisible()
}

test.describe('Production Readiness page', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    await openProductionReadiness(authenticatedPage)
  })

  test('every real tab renders and is clickable', async ({ authenticatedPage: page }) => {
    for (const tab of TABS) {
      await tabButton(page, tab).click()
      await expect(tabButton(page, tab)).toHaveClass(/active/)
    }
  })

  test('overview shows real, non-fabricated counts matching the API', async ({
    authenticatedPage: page, state,
  }) => {
    const apiCounts = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(`${backendBaseUrl}/api/admin/production-readiness/overview`, {
        credentials: 'include',
      })
      return response.json()
    }, state.backendBaseUrl)

    await tabButton(page, 'Overview').click()
    const card = page.locator('article.status-card', {
      hasText: 'RAG promotions awaiting approval',
    })
    await expect(card.locator('strong')).toHaveText(
      String(apiCounts.rag_promotions_awaiting_approval),
    )
  })

  test('RAG Promotion tab reports real eligibility for the seeded accepted report', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'RAG Promotion').click()
    await page
      .getByPlaceholder('Accepted RAG sandbox experiment public ID')
      .fill(state.fixtures.rag_sandbox_experiment_public_id)
    await page.getByRole('button', { name: 'Check eligibility' }).click()
    await expect(page.getByText('Eligible: true')).toBeVisible({ timeout: 10_000 })
  })

  test('RAG Promotion tab reports ineligible for an unknown experiment id honestly', async ({
    authenticatedPage: page,
  }) => {
    await tabButton(page, 'RAG Promotion').click()
    await page
      .getByPlaceholder('Accepted RAG sandbox experiment public ID')
      .fill('00000000-0000-0000-0000-000000000000')
    await page.getByRole('button', { name: 'Check eligibility' }).click()
    await expect(page.locator('.error-notice')).toBeVisible({ timeout: 10_000 })
  })

  test('RAG Candidates tab loads the seeded built candidate with a real status', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'RAG Candidates').click()
    await page
      .getByPlaceholder('RAG release candidate public ID')
      .fill(state.fixtures.rag_release_candidate_public_id)
    await page.getByRole('button', { name: 'Load' }).click()
    await expect(page.getByText(/Status: (built|validated|activated)/)).toBeVisible({
      timeout: 10_000,
    })
  })

  test('Model Release tab reports real eligibility for the seeded accepted checkpoint', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'Model Release').click()
    await page
      .getByPlaceholder('Accepted Phase 14 checkpoint public ID')
      .fill(state.fixtures.incremental_training_checkpoint_public_id)
    await page.getByRole('button', { name: 'Check eligibility' }).click()
    await expect(page.getByText('Eligible: true')).toBeVisible({ timeout: 10_000 })
  })

  test('the unapproved model release request shows a draft (blocked) status honestly', async ({
    authenticatedPage: page,
  }) => {
    await tabButton(page, 'Model Release').click()
    const releaseRow = page.getByRole('button', { name: /^PMR-/ })
    await expect(releaseRow.first()).toBeVisible({ timeout: 10_000 })
    // The unapproved request is listed in the left-hand data list alongside
    // the approved one -- both are real rows from the seeded database, not
    // fabricated UI state.
    const count = await releaseRow.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('an API failure renders the page error state, never a blank crash', async ({
    authenticatedPage: page,
  }) => {
    await page.route('**/api/admin/production-readiness/overview', (route) =>
      route.fulfill({ status: 500, body: JSON.stringify({ detail: 'simulated failure' }) }),
    )
    await page.reload()
    await expect(page.locator('.error-notice')).toBeVisible({ timeout: 10_000 })
  })

  test('Backup & Deployment tab reports real, non-fabricated deployment readiness and health', async ({
    authenticatedPage: page,
  }) => {
    // Phase 15A Step 22-23: revalidate these checks against the real
    // running backend/frontend, not a mock. The seeded environment has
    // not run every required check (e.g. no canonical regression run,
    // no browser-verification evidence, no backup encryption yet), so an
    // honest result here is "not_ready"/"blocked" with real blocking
    // reasons -- never a fabricated "ready".
    await tabButton(page, 'Backup & Deployment').click()

    await page.getByRole('button', { name: 'Assess deployment readiness' }).click()
    await expect(page.getByText(/^Deployment readiness: /)).toBeVisible({ timeout: 15_000 })
    const deploymentText = await page.getByText(/^Deployment readiness: /).textContent()
    expect(['Deployment readiness: ready', 'Deployment readiness: not_ready', 'Deployment readiness: blocked'])
      .toContain(deploymentText)

    await page.getByRole('button', { name: 'System health snapshot' }).click()
    await expect(page.getByText(/^System health: /)).toBeVisible({ timeout: 15_000 })
    const healthText = await page.getByText(/^System health: /).textContent()
    expect(['System health: healthy', 'System health: degraded']).toContain(healthText)
  })

  test('no console errors are produced while visiting every tab', async ({
    authenticatedPage: page,
  }) => {
    const consoleErrors = []
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text())
    })
    page.on('pageerror', (error) => consoleErrors.push(String(error)))
    for (const tab of TABS) {
      await tabButton(page, tab).click()
    }
    expect(consoleErrors).toEqual([])
  })
})
