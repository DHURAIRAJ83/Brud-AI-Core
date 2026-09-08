// Phase 2.7D: Core Model lifecycle UI, driven through the real browser
// against the real, isolated backend (never by importing React components
// or calling Python services directly). Covers Part 6's TESTS A-L: Create
// Family, Create Config, Validate Config (both the golden and the
// deliberately-invalid path), Create Version, Initialize, Architecture
// Verification, Smoke Test, Stage, UI Refresh (reload proves persistence
// comes from the backend, not frontend memory), Failure Handling (a real
// unique-constraint conflict surfaced honestly, no 500), and
// Authorization/CSRF for this specific route surface.
//
// TEST I (training integration) is intentionally not exercised here: the
// mission scopes it to MB-22/TorchTrainingAdapter's own real training
// path, which this page's "stage" boundary deliberately does not reach
// (see CoreModelPage.jsx's safety-guard note) -- it is out of scope for
// this spec by design, not an oversight.

import { expect, openSidebarPage, test } from '../fixtures.js'

async function openCoreModel(page) {
  await openSidebarPage(page, 'Core Model')
  await expect(page.getByRole('heading', { name: 'Core Model', level: 1 })).toBeVisible()
}

function tab(page, name) {
  return page.locator('.tabs').getByRole('button', { name, exact: true })
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

test.describe('Core Model lifecycle (isolated database)', () => {
  // Each test advances real, shared lifecycle state (a family name must
  // stay unique, a version's real lifecycle_status only ever moves
  // forward) -- not safely re-runnable against itself, matching the same
  // discipline already established in 04-rag-workflow.spec.js and
  // 05-model-workflow.spec.js.
  test.describe.configure({ retries: 0 })

  test.beforeEach(async ({ authenticatedPage }) => {
    await openCoreModel(authenticatedPage)
  })

  test('family -> config -> validate -> version -> initialize -> verify -> smoke test -> stage (real lifecycle)', async ({
    authenticatedPage: page, state,
  }, testInfo) => {
    testInfo.setTimeout(90_000)
    const suffix = Date.now().toString(36)
    const familyName = `e2e-lifecycle-${suffix}`

    // -- TEST A: Create Family --
    await tab(page, 'Families').click()
    await page.getByLabel('Name', { exact: true }).fill(familyName)
    await page.getByLabel('Display name').fill(`E2E Lifecycle ${suffix}`)
    await page.getByRole('button', { name: 'Create family' }).click()
    await expect(page.getByRole('cell', { name: familyName })).toBeVisible({ timeout: 10_000 })

    // -- TEST B: Create Config (real architecture values, real tokenizer) --
    await tab(page, 'Configurations').click()
    const configName = `e2e-config-${suffix}`
    await page.getByLabel('Name', { exact: true }).fill(configName)
    await page.getByLabel('Tokenizer version').selectOption(state.fixtures.core_model_tokenizer_version_public_id)
    await page.getByLabel('context length (optional override)').fill('32')
    await page.getByLabel('hidden size (optional override)').fill('32')
    await page.getByLabel('intermediate size (optional override)').fill('64')
    await page.getByLabel('num hidden layers (optional override)').fill('2')
    await page.getByLabel('num attention heads (optional override)').fill('4')
    await page.getByLabel('num key value heads (optional override)').fill('4')
    await page.getByRole('button', { name: 'Estimate parameters' }).click()
    await expect(page.getByText(/^Estimated parameters:/)).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: 'Create config' }).click()
    const configRow = page.locator('tr').filter({ hasText: configName }).first()
    await expect(configRow).toBeVisible({ timeout: 10_000 })
    await expect(configRow).toContainText('draft')

    // -- TEST C: Validate Config (golden path) --
    await configRow.getByRole('button', { name: 'Validate' }).click()
    await expect(configRow).toContainText('validated', { timeout: 10_000 })

    // -- TEST D: Create Version --
    await tab(page, 'Versions').click()
    await page.getByLabel('Family').selectOption({ label: `E2E Lifecycle ${suffix}` })
    await page.getByLabel('Validated config').selectOption({ label: `${configName} v1` })
    const versionLabel = `v0.1-${suffix}`
    await page.getByLabel('Version', { exact: true }).fill(versionLabel)
    await page.getByRole('button', { name: 'Create version' }).click()
    const versionButton = page.getByRole('button', { name: new RegExp(`^${versionLabel}`) })
    await expect(versionButton).toBeVisible({ timeout: 10_000 })
    await versionButton.click()
    await expect(page.getByText('Status draft')).toBeVisible({ timeout: 10_000 })
    const versionMatch = await fetchJson(
      page, state.backendBaseUrl,
      `/api/admin/core-models/versions?page_size=100`,
    )
    const versionRow = versionMatch.items.find((item) => item.version === versionLabel)
    expect(versionRow).toBeTruthy()
    expect(versionRow.lifecycle_status).toBe('draft')
    const versionId = versionRow.public_id

    // -- TEST E: Initialize (verify actual state change, not just a UI label) --
    await page.getByRole('button', { name: 'Initialize' }).click()
    await expect(page.getByText('Status initialized')).toBeVisible({ timeout: 15_000 })
    let backendVersion = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/versions/${versionId}`)
    expect(backendVersion.lifecycle_status).toBe('initialized')
    expect(backendVersion.weights_checksum_sha256).toBeTruthy()

    // -- TEST F: Architecture Verification (verify returned result persisted) --
    await page.getByRole('button', { name: 'Verify architecture' }).click()
    await expect(page.getByText('Status architecture_verified')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('cell', { name: 'configuration_valid' })).toBeVisible({ timeout: 10_000 })
    backendVersion = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/versions/${versionId}`)
    expect(backendVersion.lifecycle_status).toBe('architecture_verified')
    const checks = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/versions/${versionId}/checks`)
    expect(checks.items.length).toBeGreaterThan(0)
    expect(checks.items.every((item) => item.status === 'pass')).toBe(true)

    // -- TEST G: Smoke Test (real tiny_overfit training loop) --
    await page.getByRole('button', { name: 'Run smoke test' }).click()
    await expect(page.getByText('Status smoke_tested')).toBeVisible({ timeout: 30_000 })
    backendVersion = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/versions/${versionId}`)
    expect(backendVersion.lifecycle_status).toBe('smoke_tested')
    const checkpoints = await fetchJson(
      page, state.backendBaseUrl, `/api/admin/core-models/versions/${versionId}/checkpoints`,
    )
    expect(checkpoints.items.some((item) => item.checkpoint_type === 'smoke_test')).toBe(true)

    // -- TEST H: Stage (verify persisted state) --
    await page.getByRole('button', { name: 'Stage', exact: true }).click()
    await expect(page.getByText('Status staging')).toBeVisible({ timeout: 15_000 })
    backendVersion = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/versions/${versionId}`)
    expect(backendVersion.lifecycle_status).toBe('staging')

    // Safety guard (Part 5): no Activate control exists on this page at all.
    await expect(page.getByRole('button', { name: 'Activate', exact: true })).toHaveCount(0)

    // -- TEST J: UI Refresh -- reload the page and re-select the same
    // version; the "staging" status must come back from a fresh GET, not
    // from anything cached in frontend memory (a full reload clears it).
    await page.reload()
    await openCoreModel(page)
    await tab(page, 'Versions').click()
    await page.getByRole('button', { name: new RegExp(`^${versionLabel}`) }).click()
    await expect(page.getByText('Status staging')).toBeVisible({ timeout: 10_000 })
  })

  test('an invalid configuration is reported honestly, not hidden or crashed past', async ({
    authenticatedPage: page, state,
  }) => {
    await tab(page, 'Configurations').click()
    const row = page.locator('tr').filter({ hasText: 'e2e-invalid-config' }).first()
    // fields=['name','config_version','status',...] -- the config's own
    // name ("e2e-invalid-config") contains the literal substring
    // "invalid", so asserting on the whole row's text would pass whether
    // or not validation actually ran; the status column specifically is
    // the real signal.
    const statusCell = row.locator('td').nth(2)
    await expect(row).toBeVisible()
    await expect(statusCell).toHaveText('draft')
    await row.getByRole('button', { name: 'Validate' }).click()
    await expect(statusCell).toHaveText('invalid', { timeout: 10_000 })

    const backendConfig = await fetchJson(
      page, state.backendBaseUrl,
      `/api/admin/core-models/configs/${state.fixtures.core_model_invalid_config_public_id}`,
    )
    expect(backendConfig.status).toBe('invalid')
  })

  test('a duplicate family name is rejected with a real error, not a 500 or silent failure', async ({
    authenticatedPage: page, state,
  }) => {
    // -- TEST K: Failure Handling -- the UI does not pre-check name
    // uniqueness client-side, so submitting the same name twice reaches
    // the real backend's UNIQUE constraint on core_model_families.name,
    // which the app's own ConflictError/exception-handler layer must
    // turn into a clean 409, not an internal_error/500.
    await tab(page, 'Families').click()
    const duplicateName = `e2e-duplicate-${Date.now().toString(36)}`
    await page.getByLabel('Name', { exact: true }).fill(duplicateName)
    await page.getByLabel('Display name').fill('First')
    await page.getByRole('button', { name: 'Create family' }).click()
    await expect(page.getByRole('cell', { name: duplicateName })).toBeVisible({ timeout: 10_000 })

    await page.getByLabel('Name', { exact: true }).fill(duplicateName)
    await page.getByLabel('Display name').fill('Second (duplicate)')
    await page.getByRole('button', { name: 'Create family' }).click()
    await expect(page.locator('.error-notice')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.error-notice')).not.toContainText('Internal server error')

    const families = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/families?page_size=100`)
    const matches = families.items.filter((item) => item.name === duplicateName)
    expect(matches).toHaveLength(1)
  })

  test('mutating the Core Model API without a CSRF header or session is rejected, not silently allowed', async ({
    authenticatedPage: page, state,
  }) => {
    // -- TEST L: Authorization/CSRF for this route surface specifically --
    const withoutCsrf = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(`${backendBaseUrl}/api/admin/core-models/families`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'should-not-be-created', display_name: 'Should not be created' }),
      })
      return response.status
    }, state.backendBaseUrl)
    expect(withoutCsrf).toBe(403)

    const unauthenticated = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(`${backendBaseUrl}/api/admin/core-models/families`, {
        method: 'POST', credentials: 'omit',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'should-not-be-created-2', display_name: 'Should not be created' }),
      })
      return response.status
    }, state.backendBaseUrl)
    expect([401, 403]).toContain(unauthenticated)

    const families = await fetchJson(page, state.backendBaseUrl, `/api/admin/core-models/families?page_size=100`)
    expect(families.items.some((item) => item.name.startsWith('should-not-be-created'))).toBe(false)
  })
})
