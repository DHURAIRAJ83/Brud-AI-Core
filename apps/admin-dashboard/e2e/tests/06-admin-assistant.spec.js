import { expect, test } from '../fixtures.js'

const FORBIDDEN_ACTION_MARKERS = [
  'approve_rag_promotion', 'approve_model_release', 'activate_rag', 'activate_model',
  'rollback_rag', 'rollback_model', 'build_candidate', 'validate_candidate',
]

test.describe('Admin Assistant', () => {
  test('the floating widget opens, shows mode filter and language selector', async ({
    authenticatedPage: page,
  }) => {
    await page.getByRole('button', { name: 'Open Admin Assistant' }).click()
    const dialog = page.getByRole('dialog', { name: 'Brud AI Admin Assistant' })
    await expect(dialog).toBeVisible()
    const modeNav = dialog.getByRole('navigation', { name: 'Assistant mode filter' })
    await expect(modeNav).toBeVisible()
    for (const mode of ['Guide', 'Data', 'Governance', 'RAG', 'Model', 'System']) {
      await expect(modeNav.getByRole('button', { name: mode, exact: true })).toBeVisible()
    }
    await expect(dialog.getByLabel('Reply language')).toBeVisible()
    await page.getByRole('button', { name: 'Close Admin Assistant' }).click()
    await expect(page.getByRole('dialog', { name: 'Brud AI Admin Assistant' })).toHaveCount(0)
  })

  test('the full Admin Assistant page renders its three real sections', async ({
    authenticatedPage: page,
  }) => {
    await page.getByRole('button', { name: 'Admin Assistant', exact: true }).click()
    // Topbar's own <h1> also reads "Admin Assistant" (it just echoes the
    // active page name) -- level:2 scopes to this page's own heading.
    await expect(page.getByRole('heading', { name: 'Admin Assistant', level: 2 })).toBeVisible()
    const nav = page.getByRole('navigation', { name: 'Admin Assistant sections' })
    for (const tabName of ['Guidance', 'Propose an Action', 'Proposals & Admin Review']) {
      await expect(nav.getByRole('button', { name: tabName })).toBeVisible()
    }
  })

  test('never offers a production approve/activate/rollback action type', async ({
    authenticatedPage: page,
  }) => {
    await page.getByRole('button', { name: 'Admin Assistant', exact: true }).click()
    await page
      .getByRole('navigation', { name: 'Admin Assistant sections' })
      .getByRole('button', { name: 'Propose an Action' })
      .click()
    const actionSelect = page.getByLabel('Action type')
    await expect(actionSelect).toBeVisible()
    await expect(actionSelect.locator('option').first()).toBeAttached({ timeout: 10_000 })
    await expect
      .poll(async () => (await actionSelect.locator('option').allTextContents()).length, {
        timeout: 10_000,
      })
      .toBeGreaterThan(0)
    const optionValues = await actionSelect.locator('option').allTextContents()
    expect(optionValues.length).toBeGreaterThan(0)
    for (const marker of FORBIDDEN_ACTION_MARKERS) {
      expect(optionValues.some((value) => value.includes(marker))).toBe(false)
    }
    expect(optionValues).toContain('run_production_api_abuse_readiness_check')
  })

  test('a real propose -> review -> execute cycle runs a genuine safety check', async ({
    authenticatedPage: page,
  }) => {
    await page.getByRole('button', { name: 'Admin Assistant', exact: true }).click()
    const nav = page.getByRole('navigation', { name: 'Admin Assistant sections' })

    await nav.getByRole('button', { name: 'Propose an Action' }).click()
    await page.getByLabel('Action type').selectOption('run_production_api_abuse_readiness_check')
    await page.getByLabel('Target type').fill('production_readiness_system')
    await page.getByLabel('Target public ID (e.g. dataset record ID)').fill('system')
    await page
      .getByLabel('Summary shown to the reviewing admin')
      .fill('e2e: run the API-abuse readiness check')
    await page.getByLabel('Request payload (JSON)').fill('{}')
    await page.getByRole('button', { name: 'Create proposal' }).click()

    await expect(
      page.getByRole('navigation', { name: 'Admin Assistant sections' }).getByRole('button', {
        name: 'Proposals & Admin Review',
      }),
    ).toHaveClass(/active/)
    const row = page.getByRole('row', { name: /e2e: run the API-abuse readiness check/ })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.getByRole('button', { name: 'Review' }).click()

    await expect(page.getByRole('button', { name: 'Approve' })).toBeVisible()
    // The Admin Assistant's own "Approve" here means "allow this proposal
    // to execute" (governance review of the proposal itself) -- it is not,
    // and must never become, a production model/RAG approval, activation,
    // or rollback control.
    await page.getByRole('button', { name: 'Approve' }).click()

    await expect(page.getByRole('button', { name: 'Execute through secured service' })).toBeVisible({
      timeout: 10_000,
    })
    await page.getByRole('button', { name: 'Execute through secured service' }).click()

    await expect(page.getByText(/"result_status"/)).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/"execution_status":\s*"succeeded"/)).toBeVisible()
  })

  test('the reply-language preference can be changed and is persisted', async ({
    authenticatedPage: page, state,
  }) => {
    await page.getByRole('button', { name: 'Admin Assistant', exact: true }).click()
    await page.getByLabel('Reply language').selectOption('tamil')
    await expect(page.getByLabel('Reply language')).toHaveValue('tamil')

    // The PATCH triggered by selectOption() may still be in flight; poll
    // the backend directly rather than assuming any particular DOM signal
    // marks its completion.
    await expect
      .poll(
        async () =>
          page.evaluate(async (backendBaseUrl) => {
            const response = await fetch(
              `${backendBaseUrl}/api/admin/assistant/preferences`,
              { credentials: 'include' },
            )
            return (await response.json()).response_language
          }, state.backendBaseUrl),
        { timeout: 10_000 },
      )
      .toBe('tamil')
  })
})
