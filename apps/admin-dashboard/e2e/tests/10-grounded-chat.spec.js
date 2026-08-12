import { expect, test } from '../fixtures.js'

// "Knowledge & RAG" lives inside the collapsible "Knowledge & Retrieval"
// nav group, which starts collapsed unless the active page is already
// within it (Sidebar.jsx) -- matches the same open-if-needed pattern
// already used by 08-document-sft-workflow.spec.js / 09-document-sft-
// production-closure.spec.js.
async function openRagPage(page) {
  // Scoped to the sidebar nav specifically -- with the Admin Assistant
  // widget open (it has its own "Data" mode-filter button, unrelated to
  // this nav group), an unscoped getByRole('button', { name: 'Knowledge
  // & Retrieval' }) could otherwise collide with future widget filters.
  const sidebar = page.getByRole('navigation', { name: 'Admin modules' })
  const dataToggle = sidebar.getByRole('button', { name: 'Knowledge & Retrieval', exact: true })
  if ((await dataToggle.getAttribute('aria-expanded')) !== 'true') await dataToggle.click()
  await sidebar.getByRole('button', { name: 'Knowledge & RAG', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Knowledge & RAG', level: 2 })).toBeVisible()
}

test.describe('Grounded chat widget + live retrieval-profile switch (isolated database)', () => {
  test.describe.configure({ retries: 0 })

  test('plain chat, grounded chat with real citations, then switching the default profile changes the citation source with no page reload', async ({
    authenticatedPage: page, state,
  }) => {
    const {
      grounded_chat_query, grounded_chat_source_a_name, grounded_chat_source_b_name,
      grounded_chat_profile_b_public_id,
    } = state.fixtures

    // 1-2: open the floating Admin Assistant widget.
    await page.getByRole('button', { name: 'Open Admin Assistant' }).click()
    const dialog = page.getByRole('dialog', { name: 'Brud AI Admin Assistant' })
    await expect(dialog).toBeVisible()
    // Phase 3: the widget's chat area is now the shared ChatPanel
    // component -- input aria-label is "Message" and message/citation
    // classes are ChatPanel's own (`.chat-message-*`), not the old
    // hand-rolled widget markup.
    const input = dialog.getByLabel('Message')
    await expect(input).toBeEnabled({ timeout: 10_000 })

    // 3: send a plain chat message -- no grounded toggle, no citations.
    await input.fill('Hello, are you there?')
    await dialog.getByRole('button', { name: 'Send' }).click()
    await expect(dialog.locator('.chat-message-assistant').first()).toBeVisible({ timeout: 20_000 })
    await expect(dialog.locator('.chat-message-citations')).toHaveCount(0)

    // 4: enable grounded mode.
    await dialog.getByLabel('Use knowledge base').check()

    // 5: send a grounded message.
    await input.fill(grounded_chat_query)
    await dialog.getByRole('button', { name: 'Send' }).click()

    // 6: citations render in the UI, sourced from the seeded default
    // (retrieval profile A).
    const citations = dialog.locator('.chat-message-citations')
    await expect(citations.first()).toBeVisible({ timeout: 20_000 })
    await expect(citations.first()).toContainText(grounded_chat_source_a_name)

    // The widget's own full card is `position: fixed` bottom-right and
    // would otherwise sit on top of (and intercept clicks on) the RAG
    // page's retrieval-profile table -- minimizing collapses its body
    // to just the header bar (real UI behavior, not a workaround: the
    // widget itself never unmounts and its session/messages state is
    // untouched, matching the "still open, no reload" requirement).
    await dialog.getByRole('button', { name: 'Minimize Admin Assistant' }).click()

    // 7: change the default retrieval profile from the RAG page -- the
    // real UI action, not a direct API call.
    await openRagPage(page)
    await page.getByRole('button', { name: 'Retrieval Profiles', exact: true }).click()
    const profileBRow = page.getByRole('row', { name: /MB48 Profile b/ })
    await expect(profileBRow).toBeVisible({ timeout: 10_000 })
    await profileBRow.getByRole('button', { name: 'Set as default' }).click()
    await expect(profileBRow).toContainText('default', { timeout: 10_000 })

    // The RAG page's own "default" label can render from a read that
    // wins a race against the SET write's own commit (both are ordinary
    // concurrent SQLite connections -- the label is not a commit
    // acknowledgement). Before touching the widget, poll the backend's
    // default-retrieval-profile endpoint directly -- same pattern as
    // 06-admin-assistant.spec.js's reply-language-preference test --
    // until it genuinely reports profile B, so the switch is confirmed
    // settled rather than assumed from a DOM signal.
    await expect
      .poll(
        async () =>
          page.evaluate(async (backendBaseUrl) => {
            const response = await fetch(
              `${backendBaseUrl}/api/admin/mini-brain/llm-runtime/grounded-chat/default-retrieval-profile`,
              { credentials: 'include', cache: 'no-store' },
            )
            return (await response.json()).retrieval_profile_public_id
          }, state.backendBaseUrl),
        { timeout: 15_000 },
      )
      .toBe(grounded_chat_profile_b_public_id)

    // 8: back to the *same*, still-open widget (a real in-app SPA
    // navigation happened above, never a page reload) -- restore it and
    // send another grounded message with the identical query.
    await dialog.getByRole('button', { name: 'Restore Admin Assistant' }).click()
    await expect(dialog).toBeVisible()
    await expect(input).toBeEnabled({ timeout: 10_000 })
    await input.fill(grounded_chat_query)
    await expect(input).toHaveValue(grounded_chat_query)
    const sendButton = dialog.getByRole('button', { name: 'Send' })
    await expect(sendButton).toBeEnabled({ timeout: 10_000 })
    await sendButton.click()

    // A second citations block must actually appear (proves the second
    // send really fired and completed) before checking its content --
    // a stuck/never-sent second message would otherwise leave `.last()`
    // silently matching the first block forever.
    await expect(citations).toHaveCount(2, { timeout: 20_000 })

    // 9: the newest citation now names retrieval profile B's source --
    // proof the switch took effect immediately, with no reload in
    // between (the first citation block, still showing source A, is
    // still present higher up in the same unreloaded DOM).
    await expect(citations.last()).toContainText(grounded_chat_source_b_name)
    await expect(citations.first()).toContainText(grounded_chat_source_a_name)
  })
})
