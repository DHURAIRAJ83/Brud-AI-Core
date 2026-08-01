import { expect, loginAsE2eAdmin, test } from '../fixtures.js'

test.describe('authentication and session', () => {
  test('an unauthenticated visit always shows the login form (client-side gate)', async ({
    page,
  }) => {
    await page.context().clearCookies()
    await page.goto('/#Production Readiness')
    await expect(page.getByRole('heading', { name: 'Admin sign in' })).toBeVisible()
  })

  test('valid login reaches the dashboard', async ({ page }) => {
    await loginAsE2eAdmin(page)
    await expect(page.getByRole('navigation', { name: 'Admin modules' })).toBeVisible()
  })

  test('invalid login shows an error and does not reach the dashboard', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('Username').fill('e2e-verifier')
    await page.getByLabel('Password').fill('definitely-the-wrong-password')
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page.getByRole('alert')).toContainText('Invalid username or password')
    await expect(page.getByRole('heading', { name: 'Admin sign in' })).toBeVisible()
  })

  test('the session cookie is HttpOnly and SameSite=Strict', async ({ page, context }) => {
    await loginAsE2eAdmin(page)
    const cookies = await context.cookies()
    const sessionCookie = cookies.find((c) => c.name === 'brud_admin_session')
    expect(sessionCookie).toBeTruthy()
    expect(sessionCookie.httpOnly).toBe(true)
    expect(sessionCookie.sameSite).toBe('Strict')
  })

  // The frontend's own code always calls the backend through an absolute
  // `VITE_API_BASE_URL`-derived URL (see services/api.js), never a
  // relative `/api/...` path -- a relative path from the *page* would
  // instead hit vite.config.js's own dev-server proxy (hard-coded to
  // port 8000, the *real* dev backend, not this isolated e2e one). These
  // tests therefore call the isolated backend by its absolute URL too,
  // matching how the real app actually talks to it.

  test('a mutation without the CSRF header is rejected with 403 even with a valid session', async ({
    page, state,
  }) => {
    await loginAsE2eAdmin(page)
    const status = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(
        `${backendBaseUrl}/api/admin/production-readiness/api-abuse-readiness/assess`,
        {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' }, body: '{}',
        },
      )
      return response.status
    }, state.backendBaseUrl)
    expect(status).toBe(403)
  })

  test('a mutation with a forged CSRF header (no matching cookie) is rejected with 403', async ({
    page, state,
  }) => {
    await loginAsE2eAdmin(page)
    const status = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(
        `${backendBaseUrl}/api/admin/production-readiness/api-abuse-readiness/assess`,
        {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'forged-token-value' },
          body: '{}',
        },
      )
      return response.status
    }, state.backendBaseUrl)
    expect(status).toBe(403)
  })

  test('logout returns to the login form and revokes API access', async ({ page, state }) => {
    await loginAsE2eAdmin(page)
    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page.getByRole('heading', { name: 'Admin sign in' })).toBeVisible()

    const status = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(
        `${backendBaseUrl}/api/admin/production-readiness/overview`,
        { credentials: 'include' },
      )
      return response.status
    }, state.backendBaseUrl)
    expect(status).toBe(401)
  })

  test('a garbage/invalid session cookie is rejected the same way an expired one would be', async ({
    page, context, state,
  }) => {
    await page.goto('/')
    await context.addCookies([
      {
        name: 'brud_admin_session', value: 'not-a-real-session-token',
        domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Strict',
      },
    ])
    const status = await page.evaluate(async (backendBaseUrl) => {
      const response = await fetch(
        `${backendBaseUrl}/api/admin/production-readiness/overview`,
        { credentials: 'include' },
      )
      return response.status
    }, state.backendBaseUrl)
    expect(status).toBe(401)
  })

  test('two separate browser contexts have fully isolated sessions', async ({ browser }) => {
    const contextA = await browser.newContext()
    const contextB = await browser.newContext()
    try {
      const pageA = await contextA.newPage()
      await loginAsE2eAdmin(pageA)
      await expect(pageA.getByRole('navigation', { name: 'Admin modules' })).toBeVisible()

      const pageB = await contextB.newPage()
      await pageB.goto('/')
      await expect(pageB.getByRole('heading', { name: 'Admin sign in' })).toBeVisible()
    } finally {
      await contextA.close()
      await contextB.close()
    }
  })
})
