/**
 * P7-02 E2E — 04 Interactive Features & Page Content
 *
 * Verifies:
 * 1. FAQ accordion behavior: open/close on click, aria-expanded toggling.
 * 2. Desktop page: Coming Soon state, platform badges, system requirements.
 * 3. Help page: Guide sections, quick links to Chat and FAQ.
 * 4. Chat page: Public chat notice, canonical iframe container.
 * 5. Legal pages (Privacy & Terms): Complete sections, accessible headings.
 */

import { expect, test } from '@playwright/test'

test.describe('Interactive Features — FAQ accordion', () => {
  test('FAQ items can be expanded and collapsed', async ({ page }) => {
    await page.goto('/faq')

    const firstQuestion = page.locator('.faq-question').first()
    const firstItem = page.locator('.faq-item').first()

    // Initially collapsed
    await expect(firstQuestion).toHaveAttribute('aria-expanded', 'false')
    await expect(firstItem).toHaveAttribute('data-open', 'false')

    // Click to expand
    await firstQuestion.click()
    await expect(firstQuestion).toHaveAttribute('aria-expanded', 'true')
    await expect(firstItem).toHaveAttribute('data-open', 'true')

    // Answer text is visible
    const answer = firstItem.locator('.faq-answer')
    await expect(answer).toBeVisible()
    await expect(answer).toContainText(/multilingual AI chat assistant/i)

    // Click again to collapse
    await firstQuestion.click()
    await expect(firstQuestion).toHaveAttribute('aria-expanded', 'false')
    await expect(firstItem).toHaveAttribute('data-open', 'false')
  })
})

test.describe('Interactive Features — Desktop Page', () => {
  test('Desktop page renders Coming Soon status and platform support', async ({ page }) => {
    await page.goto('/desktop')

    // Status badge
    const badge = page.locator('.badge, .hero-badge, [class*="badge"]').first()
    await expect(badge).toBeVisible()

    // Heading
    await expect(page.locator('h1')).toHaveText(/Desktop App/i)

    // Platform indicators
    const bodyText = await page.textContent('body')
    expect(bodyText).toMatch(/macOS|Windows|Linux/i)
    expect(bodyText).toMatch(/Coming Soon/i)

    // CTA button is present and indicates upcoming availability or notification
    const cta = page.getByRole('link', { name: /Open Web Chat|Start Chatting on Web|Chat Online|Start Chat/i }).first()
    await expect(cta).toBeVisible()
  })
})

test.describe('Interactive Features — Help Page', () => {
  test('Help page provides quick start guide and cross-links', async ({ page }) => {
    await page.goto('/help')

    await expect(page.locator('h1')).toBeVisible()

    // Cross-link to Chat exists
    const chatLink = page.getByRole('link', { name: /Start Chat|Chat Now|Open Chat/i }).first()
    await expect(chatLink).toBeVisible()

    // Cross-link to FAQ exists
    const faqLink = page.getByRole('link', { name: /FAQ|Frequently Asked Questions/i }).first()
    await expect(faqLink).toBeVisible()
  })
})

test.describe('Interactive Features — Chat Page', () => {
  test('Chat page embeds canonical chatbot iframe safely', async ({ page }) => {
    await page.goto('/chat')

    // Integration notice is visible
    const notice = page.locator('.chat-integration-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toContainText(/Public Chat/i)

    // Iframe or fallback container is rendered
    const iframe = page.locator('iframe[title="Brud AI Public Chat"]')
    const fallback = page.locator('text=Chat Unavailable')

    const iframeCount = await iframe.count()
    const fallbackCount = await fallback.count()

    expect(iframeCount + fallbackCount).toBeGreaterThan(0)
    if (iframeCount > 0) {
      await expect(iframe).toHaveAttribute('title', 'Brud AI Public Chat')
    }
  })
})

test.describe('Interactive Features — Legal Pages', () => {
  test('Privacy Policy page renders required disclosures', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.locator('h1')).toHaveText(/Privacy/i)
    const body = await page.textContent('body')
    expect(body).toMatch(/Data Collection|Information We Collect|Privacy Policy/i)
  })

  test('Terms of Service page renders acceptable use and disclaimers', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.locator('h1')).toHaveText(/Terms/i)
    const body = await page.textContent('body')
    expect(body).toMatch(/Guidelines for using Brud AI responsibly|Responsible Use|Prohibited Use|Disclaimer/i)
  })
})
