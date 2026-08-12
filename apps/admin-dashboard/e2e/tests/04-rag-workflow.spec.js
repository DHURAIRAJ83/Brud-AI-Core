import { expect, openSidebarPage, test } from '../fixtures.js'

function tabButton(page, name) {
  return page
    .getByRole('navigation', { name: 'Production readiness sections' })
    .getByRole('button', { name, exact: true })
}

async function openProductionReadiness(page) {
  await openSidebarPage(page, 'Production Readiness')
  await expect(page.getByRole('heading', { name: 'Production Readiness', level: 2 })).toBeVisible()
}

test.describe('Production RAG workflow (isolated database)', () => {
  // These tests mutate real, shared, seeded state (a promotion request's
  // real status, or the seeded candidate's real lifecycle stage) -- they
  // are not safely re-runnable against themselves, so a flaky retry would
  // start from an already-advanced state instead of the expected one.
  test.describe.configure({ retries: 0 })

  test.beforeEach(async ({ authenticatedPage }) => {
    await openProductionReadiness(authenticatedPage)
  })

  test('a new promotion request stays draft until explicitly submitted and approved', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'RAG Promotion').click()
    await page
      .getByPlaceholder('RAG sandbox experiment public ID', { exact: true })
      .fill(state.fixtures.rag_sandbox_experiment_public_id)
    await page
      .getByPlaceholder('Knowledge space public ID')
      .fill(state.fixtures.knowledge_space_public_id)
    await page.getByRole('button', { name: 'Create request' }).click()

    // Creating a request only refreshes the left-hand list -- it does not
    // auto-select the new row's detail view. The newest request sorts
    // first (list is id DESC), so the real, current admin action here is
    // to open it explicitly, exactly as a human would click it.
    await page.getByRole('button', { name: /^PRP-.*draft$/ }).first().click()

    await expect(page.getByText('Status: draft')).toBeVisible({ timeout: 10_000 })
    // No approval has been requested yet -- there is no candidate to
    // activate, and the UI must never claim otherwise.
    await expect(page.getByRole('button', { name: 'Build release candidate' })).toBeVisible()

    await page.getByRole('button', { name: 'Submit for review' }).click()
    await expect(page.getByText('Status: awaiting_review')).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: 'Request approval' }).click()
    await expect(page.getByText(/^Approval: /)).toBeVisible({ timeout: 10_000 })
    // Still awaiting_review -- the approval request alone does not approve
    // anything.
    await expect(page.getByText('Status: awaiting_review')).toBeVisible()
  })

  test('building a candidate before approval is rejected by the real backend', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'RAG Promotion').click()
    await page
      .getByPlaceholder('RAG sandbox experiment public ID', { exact: true })
      .fill(state.fixtures.rag_sandbox_experiment_public_id)
    await page
      .getByPlaceholder('Knowledge space public ID')
      .fill(state.fixtures.knowledge_space_public_id)
    await page.getByRole('button', { name: 'Create request' }).click()
    await page.getByRole('button', { name: /^PRP-.*draft$/ }).first().click()
    await expect(page.getByText('Status: draft')).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: 'Build release candidate' }).click()
    await expect(page.locator('.error-notice')).toContainText(/approved/i, { timeout: 10_000 })
  })

  test('the seeded pre-approved candidate can be validated, activated, and rolled back', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'RAG Candidates').click()
    const candidateInput = page.getByPlaceholder('RAG release candidate public ID')
    await candidateInput.fill(state.fixtures.rag_release_candidate_public_id)
    await page.getByRole('button', { name: 'Load' }).click()
    await expect(page.getByText(/Status: built/)).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('Production visible: false')).toBeVisible()

    await candidateInput.fill(state.fixtures.rag_release_candidate_public_id)
    await page.getByRole('button', { name: 'Validate', exact: true }).click()
    await expect(page.getByText(/Status: validated/)).toBeVisible({ timeout: 15_000 })

    await candidateInput.fill(state.fixtures.rag_release_candidate_public_id)
    await page.getByRole('button', { name: 'Activate' }).click()
    await expect(page.getByText(/Status: activated/)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('Production visible: true')).toBeVisible()

    // This is the very first activation in its knowledge space, so there
    // is genuinely no previous profile to roll back to -- the real
    // backend rejects the rollback, and the UI must show that honestly
    // rather than pretending it succeeded.
    await candidateInput.fill(state.fixtures.rag_release_candidate_public_id)
    await page.getByRole('button', { name: 'Rollback to previous' }).click()
    await expect(page.locator('.error-notice')).toBeVisible({ timeout: 10_000 })
  })
})
