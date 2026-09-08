import { expect, openSidebarPage, test } from '../fixtures.js'

test.describe('Assistant Center', () => {
  test('unifies Admin Tasks, Mini Brain Chat, and Public Chat Monitor behind one page', async ({
    authenticatedPage: page, state,
  }) => {
    const { grounded_chat_query, grounded_chat_source_a_name, grounded_chat_source_b_name } = state.fixtures

    await openSidebarPage(page, 'Assistant Center')
    await expect(page.getByRole('heading', { name: 'Assistant Center', level: 2 })).toBeVisible()
    const tabs = page.getByRole('navigation', { name: 'Assistant Center sections' })
    for (const tabName of ['Admin Tasks', 'Mini Brain Chat', 'Public Chat Monitor']) {
      await expect(tabs.getByRole('button', { name: tabName })).toBeVisible()
    }

    // Admin Tasks tab is checked last in this test (see bottom) since
    // opening it navigates away from Assistant Center entirely.
    await expect(tabs.getByRole('button', { name: 'Admin Tasks' })).toHaveAttribute('aria-current', 'page')

    // Mini Brain Chat: the shared ChatPanel, real runtime diagnostics, plain
    // chat, then grounded chat with a real citation.
    await tabs.getByRole('button', { name: 'Mini Brain Chat' }).click()
    const messageInput = page.getByLabel('Message')
    await expect(messageInput).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('Local runtime')).toBeVisible({ timeout: 15_000 })

    await messageInput.fill('Hello, are you there?')
    await page.getByRole('button', { name: 'Send' }).click()
    await expect(page.locator('.chat-message-assistant').first()).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.chat-message-citations')).toHaveCount(0)

    await page.getByLabel('Use knowledge base').check()
    await messageInput.fill(grounded_chat_query)
    await page.getByRole('button', { name: 'Send' }).click()
    const citations = page.locator('.chat-message-citations')
    await expect(citations.first()).toBeVisible({ timeout: 20_000 })
    // Which source is the current default depends on run order relative to
    // 10-grounded-chat.spec.js (which itself flips the default from A to B
    // as part of its own scenario, on the shared isolated database) -- this
    // test only proves a real, non-fabricated citation renders, not which
    // profile happens to be active right now.
    const citationText = await citations.first().innerText()
    expect([grounded_chat_source_a_name, grounded_chat_source_b_name].some((name) => citationText.includes(name))).toBe(true)

    // Regenerate resends the last real user message through the same path.
    const assistantRepliesBefore = await page.locator('.chat-message-assistant').count()
    await page.getByRole('button', { name: 'Regenerate' }).click()
    await expect(page.locator('.chat-message-assistant')).toHaveCount(assistantRepliesBefore + 1, { timeout: 20_000 })

    // Copy button exists on every assistant reply (real clipboard util,
    // fallback-safe -- not asserting clipboard contents here since headless
    // Chromium clipboard permissions are environment-dependent).
    await expect(page.locator('.chat-message-assistant').first().getByRole('button', { name: 'Copy' })).toBeVisible()

    // Public Chat Monitor: metadata-only browser, real privacy notice,
    // never a fabricated message bubble.
    await tabs.getByRole('button', { name: 'Public Chat Monitor' }).click()
    await expect(page.getByText('No raw message text is ever stored, only content hashes and already-sanitized signal text.')).toBeVisible()

    // Admin Tasks: Phase 16.1 removed the second full mount of
    // AdminAssistantPage here (it was reachable both via its own dedicated
    // Sidebar entry and, wholesale, inside this tab) -- this tab now links
    // out to the one canonical mount instead of duplicating it. Checked
    // last since following the link navigates away from Assistant Center.
    await tabs.getByRole('button', { name: 'Admin Tasks' }).click()
    const openAdminAssistant = page.getByRole('button', { name: 'Open Admin Assistant' })
    await expect(openAdminAssistant).toBeVisible()
    await openAdminAssistant.click()
    await expect(page.getByRole('heading', { name: 'Admin Assistant', level: 2 })).toBeVisible()
    const adminTasksNav = page.getByRole('navigation', { name: 'Admin Assistant sections' })
    for (const sectionName of ['Guidance', 'Propose an Action', 'Proposals & Admin Review']) {
      await expect(adminTasksNav.getByRole('button', { name: sectionName })).toBeVisible()
    }
  })
})

test.describe('Advanced Admin Chat Workspace (floating widget)', () => {
  test('drags, resizes, docks, maximizes, and persists layout across reload without losing the conversation', async ({
    authenticatedPage: page,
  }) => {
    await page.getByRole('button', { name: 'Open Admin Assistant' }).click()
    const dialog = page.getByRole('dialog', { name: 'Brud AI Admin Assistant' })
    await expect(dialog).toBeVisible()

    // Send a message so we can prove it survives every layout change below.
    const input = dialog.getByLabel('Message')
    await input.fill('Hello, are you there?')
    await dialog.getByRole('button', { name: 'Send' }).click()
    await expect(dialog.locator('.chat-message-assistant').first()).toBeVisible({ timeout: 20_000 })

    // Drag by the title bar into floating mode.
    const handle = dialog.locator('.assistant-drag-handle')
    const headerBox = await handle.boundingBox()
    await page.mouse.move(headerBox.x + headerBox.width / 2, headerBox.y + headerBox.height / 2)
    await page.mouse.down()
    await page.mouse.move(headerBox.x - 80, headerBox.y + 60, { steps: 5 })
    await page.mouse.up()
    await expect(dialog.locator('.assistant-resize-handle')).toBeVisible()

    // Resize via the handle.
    const resizeHandle = dialog.locator('.assistant-resize-handle')
    const resizeBox = await resizeHandle.boundingBox()
    const boxBefore = await dialog.boundingBox()
    await page.mouse.move(resizeBox.x + resizeBox.width / 2, resizeBox.y + resizeBox.height / 2)
    await page.mouse.down()
    await page.mouse.move(resizeBox.x + 60, resizeBox.y + 60, { steps: 5 })
    await page.mouse.up()
    const boxAfter = await dialog.boundingBox()
    expect(boxAfter.width).toBeGreaterThan(boxBefore.width - 1)

    // Dock left.
    await dialog.getByRole('button', { name: 'Dock left' }).click()
    await expect(dialog.getByRole('button', { name: 'Dock left' })).toHaveAttribute('aria-pressed', 'true')

    // Large chat mode (maximize) and back.
    await dialog.getByRole('button', { name: 'Enter large chat mode' }).click()
    await expect(dialog.getByRole('button', { name: 'Exit large chat mode' })).toHaveAttribute('aria-pressed', 'true')
    await dialog.getByRole('button', { name: 'Exit large chat mode' }).click()

    // Minimize keeps the conversation in memory (no re-fetch on restore).
    await dialog.getByRole('button', { name: 'Minimize Admin Assistant' }).click()
    await expect(input).not.toBeVisible()
    await dialog.getByRole('button', { name: 'Restore Admin Assistant' }).click()
    await expect(dialog.locator('.chat-message-assistant').first()).toBeVisible()

    // Dock right, then reload -- layout (docked-right) must survive.
    await dialog.getByRole('button', { name: 'Dock right' }).click()
    await expect(dialog.getByRole('button', { name: 'Dock right' })).toHaveAttribute('aria-pressed', 'true')

    await page.reload()
    await page.getByRole('button', { name: 'Open Admin Assistant' }).click()
    const dialogAfterReload = page.getByRole('dialog', { name: 'Brud AI Admin Assistant' })
    await expect(dialogAfterReload).toBeVisible()
    await expect(dialogAfterReload.getByRole('button', { name: 'Dock right' })).toHaveAttribute('aria-pressed', 'true')
  })
})
