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

// Phase 1 grouped-navigation redesign moved every top-level sidebar page
// except "Overview" behind a collapsible group toggle. Existing specs that
// click a page's sidebar button directly (a pattern established before the
// regrouping) need that page's group expanded first. Rather than hardcode
// which group owns which key here (which would go stale on the next
// regrouping), this expands every not-yet-open group toggle until the
// target button is actually visible, then clicks it -- works whether the
// page is ungrouped, already visible, or nested in any group.
export async function openSidebarPage(page, key) {
  const sidebar = page.getByRole('navigation', { name: 'Admin modules' })
  const target = sidebar.getByRole('button', { name: key, exact: true })
  if (!(await target.isVisible().catch(() => false))) {
    const toggles = await sidebar.locator('.nav-group-toggle').all()
    for (const toggle of toggles) {
      if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click()
    }
  }
  await target.click()
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
