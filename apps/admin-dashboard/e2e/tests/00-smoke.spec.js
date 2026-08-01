import { expect, test } from '../fixtures.js'

test('isolated backend + frontend are reachable and a seeded admin can log in', async ({
  page,
  state,
}) => {
  expect(state.fixtures.admin_username).toBe('e2e-verifier')
  expect(state.fixtures.rag_sandbox_experiment_public_id).toBeTruthy()
  expect(state.fixtures.model_release_request_public_id).toBeTruthy()

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Admin sign in' })).toBeVisible()

  await page.getByLabel('Username').fill(state.fixtures.admin_username)
  await page.getByLabel('Password').fill(state.fixtures.admin_password)
  await page.getByRole('button', { name: /sign in/i }).click()

  await expect(page.getByRole('navigation', { name: 'Admin modules' })).toBeVisible({
    timeout: 10_000,
  })
  const consoleErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  await page.reload()
  await expect(page.getByRole('navigation', { name: 'Admin modules' })).toBeVisible({
    timeout: 10_000,
  })
  expect(consoleErrors).toEqual([])
})
