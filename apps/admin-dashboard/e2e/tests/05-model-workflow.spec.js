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

async function fetchJson(page, backendBaseUrl, path) {
  return page.evaluate(
    async ([base, p]) => {
      const response = await fetch(`${base}${p}`, { credentials: 'include' })
      return response.json()
    },
    [backendBaseUrl, path],
  )
}

test.describe('Production model release workflow (isolated database)', () => {
  test.describe.configure({ retries: 0 })

  test.beforeEach(async ({ authenticatedPage }) => {
    await openProductionReadiness(authenticatedPage)
  })

  test('an unapproved release request cannot be activated', async ({
    authenticatedPage: page, state,
  }) => {
    await tabButton(page, 'Canary & Activation').click()
    await page
      .getByPlaceholder('Release request public ID')
      .fill(state.fixtures.unapproved_model_release_request_public_id)
    await page
      .getByPlaceholder('Assignment public ID')
      .fill(state.fixtures.inference_model_assignment_public_id)
    await page.getByRole('button', { name: 'Activate', exact: true }).click()
    await expect(page.locator('.error-notice')).toBeVisible({ timeout: 10_000 })

    const request = await fetchJson(
      page, state.backendBaseUrl,
      `/api/admin/production-readiness/model/release-requests/`
        + `${state.fixtures.unapproved_model_release_request_public_id}`,
    )
    expect(request.status).toBe('draft')
  })

  test('validated request -> approval -> rollback plan -> real activation -> rollback', async ({
    authenticatedPage: page, state,
  }) => {
    // -- approve the seeded, already-validated release request --
    // (`run_validation()` does not require a prior "submit for review"
    // step -- the seed fixture is already `validated`, so "Submit for
    // review" is not part of this request's real remaining path; the
    // "unapproved" fixture used in the previous test exercises the
    // still-`draft` state instead.)
    await tabButton(page, 'Model Release').click()
    await page
      .getByRole('button', { name: new RegExp(`^PMR-.*validated$`) })
      .first()
      .click()
    await expect(page.getByText('Status: validated')).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: 'Request approval' }).click()
    await expect(page.getByText(/^Approval: /)).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: 'Approve', exact: true }).click()
    await expect(page.getByText('Status: approved')).toBeVisible({ timeout: 10_000 });

    // -- create + validate a rollback plan, then activate for real (isolated db) --
    // The rollback-plan form already defaults `target_type` to "model" --
    // no need to touch the select. A plan with zero rollback steps can
    // never be validated by the real backend (ValidationError), so the
    // steps textarea must be filled before submitting.
    await tabButton(page, 'Canary & Activation').click()
    await page.getByPlaceholder('Rollback steps (one per line)').fill('restore previous model assignment')
    await page.getByRole('button', { name: 'Create plan' }).click()
    await expect(page.getByText(/^Plan: /)).toBeVisible({ timeout: 10_000 })
    const planText = await page.getByText(/^Plan: /).textContent()
    const rollbackPlanId = planText.replace('Plan: ', '').trim()
    await page.getByRole('button', { name: 'Validate plan' }).click()

    // "Validate plan" gives no visible DOM confirmation on success (it only
    // clears panelError) -- poll the real backend so we don't race ahead to
    // "Activate" while the PATCH is still in flight.
    await expect
      .poll(
        async () =>
          (await fetchJson(page, state.backendBaseUrl, `/api/admin/production-readiness/rollback-plans/${rollbackPlanId}`)).status,
        { timeout: 10_000 },
      )
      .toBe('verified')

    await page
      .getByPlaceholder('Release request public ID')
      .fill(state.fixtures.model_release_request_public_id)
    await page
      .getByPlaceholder('Assignment public ID')
      .fill(state.fixtures.inference_model_assignment_public_id)
    await page.getByRole('button', { name: 'Activate', exact: true }).click()

    await expect
      .poll(
        async () =>
          (
            await fetchJson(
              page, state.backendBaseUrl,
              `/api/admin/production-readiness/model/release-requests/`
                + `${state.fixtures.model_release_request_public_id}`,
            )
          ).status,
        { timeout: 15_000 },
      )
      .toBe('activated')

    // The rollback plan was created without a `current_active_version`
    // (this is the assignment's first activation, so there genuinely is
    // no previous version to roll back to) -- the real backend rejects
    // the rollback, and the UI must show that honestly rather than
    // pretending it succeeded. This mirrors the equivalent, already-
    // verified RAG-candidate rollback rejection in 04-rag-workflow.spec.js.
    await page
      .getByPlaceholder('Release request public ID')
      .fill(state.fixtures.model_release_request_public_id)
    await page
      .getByPlaceholder('Assignment public ID')
      .fill(state.fixtures.inference_model_assignment_public_id)
    await page.getByRole('button', { name: 'Rollback', exact: true }).click()
    await expect(page.locator('.error-notice')).toBeVisible({ timeout: 10_000 })

    const request = await fetchJson(
      page, state.backendBaseUrl,
      `/api/admin/production-readiness/model/release-requests/`
        + `${state.fixtures.model_release_request_public_id}`,
    )
    expect(request.status).toBe('activated')
  })
})
