// Shared Playwright fixtures for the Phase 15A browser-automation suite.
// `state` exposes everything global-setup.js seeded (admin credentials,
// every fixture's public_id); `authenticatedPage` is a page that has
// already logged in as the dedicated e2e admin account, ready to use.

import { test as base, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const STATE_FILE = path.join(__dirname, '.e2e-state.json')

export function readE2eState() {
  return JSON.parse(readFileSync(STATE_FILE, 'utf-8'))
}

export async function loginAsE2eAdmin(page) {
  const state = readE2eState()
  await page.goto('/')
  await page.getByLabel('Username').fill(state.fixtures.admin_username)
  await page.getByLabel('Password').fill(state.fixtures.admin_password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page.getByRole('navigation', { name: 'Admin modules' })).toBeVisible({
    timeout: 10_000,
  })
  return state
}

export const test = base.extend({
  state: async ({}, use) => {
    await use(readE2eState())
  },
  authenticatedPage: async ({ page }, use) => {
    await loginAsE2eAdmin(page)
    await use(page)
  },
})

export { expect }
