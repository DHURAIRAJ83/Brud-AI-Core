import { expect, openSidebarPage, test } from '../fixtures.js'

test.describe('Brud Mini Brain workspace (Phase 4A: chat consolidation + hash persistence)', () => {
  test('switches tabs, chats through the shared ChatPanel (plain + grounded + regenerate + copy), deep-links from the widget, and persists the active tab across a refresh', async ({
    authenticatedPage: page, state,
  }) => {
    const { grounded_chat_query, grounded_chat_source_a_name, grounded_chat_source_b_name } = state.fixtures

    await openSidebarPage(page, 'Brud Mini Brain')
    await expect(page.getByRole('heading', { name: 'Brud Mini Brain', level: 2 })).toBeVisible()

    // Scoped to main content -- the sidebar has its own top-level
    // "Overview" nav button that would otherwise collide.
    const main = page.getByRole('main')

    // Switch through a handful of real top-level tabs -- each must render
    // without a generic crash banner.
    for (const tabName of ['Settings', 'Diagnostics', 'Runtime', 'Overview']) {
      await main.getByRole('button', { name: tabName, exact: true }).click()
      await expect(main.getByRole('button', { name: tabName, exact: true })).toHaveClass(/active/)
    }
    await expect(page.locator('.error-banner')).toHaveCount(0)

    // The "Grounded Chat Test (MB-37)" panel is now the shared ChatPanel
    // (compact) -- always visible above the tab bar regardless of tab.
    const gcPanel = page.locator('.chat-panel-compact')
    await expect(gcPanel).toBeVisible()
    const gcInput = gcPanel.getByLabel('Message')

    await gcInput.fill('Hello, are you there?')
    await gcPanel.getByRole('button', { name: 'Send' }).click()
    await expect(gcPanel.locator('.chat-message-assistant').first()).toBeVisible({ timeout: 20_000 })
    await expect(gcPanel.locator('.chat-message-citations')).toHaveCount(0)

    await gcPanel.getByLabel('Use knowledge base').check()
    await gcInput.fill(grounded_chat_query)
    await gcPanel.getByRole('button', { name: 'Send' }).click()
    const citations = gcPanel.locator('.chat-message-citations')
    await expect(citations.first()).toBeVisible({ timeout: 20_000 })
    // Which source is the current default depends on run order relative to
    // other specs that flip it (10-grounded-chat.spec.js) -- this only
    // proves a real, non-fabricated citation renders.
    const citationText = await citations.first().innerText()
    expect([grounded_chat_source_a_name, grounded_chat_source_b_name].some((name) => citationText.includes(name))).toBe(true)

    const repliesBefore = await gcPanel.locator('.chat-message-assistant').count()
    await gcPanel.getByRole('button', { name: 'Regenerate' }).click()
    await expect(gcPanel.locator('.chat-message-assistant')).toHaveCount(repliesBefore + 1, { timeout: 20_000 })
    await expect(gcPanel.locator('.chat-message-assistant').first().getByRole('button', { name: 'Copy' })).toBeVisible()

    // Widget deep-link: "Open Mini Brain Assistant" navigates here and
    // opens Assistant Intelligence's Chat sub-tab (the full ChatPanel).
    await page.getByRole('button', { name: 'Open Admin Assistant' }).click()
    await page.getByRole('button', { name: 'Open Mini Brain Assistant / Mini Brain Assistant திற' }).click()
    await expect(page.getByRole('heading', { name: 'Brud Mini Brain', level: 2 })).toBeVisible()
    await expect(main.getByRole('button', { name: 'Assistant Intelligence', exact: true })).toHaveClass(/active/)
    const fullPanel = page.locator('.chat-panel-full')
    await expect(fullPanel).toBeVisible()

    // Hash persistence: switch to a real tab, reload, confirm it survives.
    await main.getByRole('button', { name: 'Logs', exact: true }).click()
    await expect(page).toHaveURL(/tab=Logs/)
    await page.reload()
    await expect(page.getByRole('main').getByRole('button', { name: 'Logs', exact: true })).toHaveClass(/active/)
  })
})
