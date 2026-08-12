import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, openSidebarPage, test } from '../fixtures.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..')

function pythonExecutable() {
  const venvPython = path.join(REPO_ROOT, 'venv', 'bin', 'python')
  return existsSync(venvPython) ? venvPython : 'python3'
}

// Same real-PDF-generation technique as 08-document-sft-workflow.spec.js --
// a genuinely extractable PDF via PyMuPDF, not a hand-rolled byte string.
function makeRealPdfBuffer() {
  const dir = mkdtempSync(path.join(tmpdir(), 'brud-e2e-wizard-pdf-'))
  const pdfPath = path.join(dir, 'wizard-sample.pdf')
  execFileSync(pythonExecutable(), [
    '-c',
    `
import fitz
pdf = fitz.open()
page = pdf.new_page()
page.insert_text((72, 72), "Brud AI is a Tamil-first assistant platform used for internal pilot testing of the data workspace wizard.")
pdf.save(${JSON.stringify(pdfPath)})
pdf.close()
`,
  ])
  return readFileSync(pdfPath)
}

async function openWizard(page) {
  await openSidebarPage(page, 'Data Workspace Wizard')
  await expect(page.getByRole('heading', { name: 'Data Workspace Wizard', level: 2 })).toBeVisible()
}

// Scoped to the step-progress sidebar specifically -- several step labels
// ("Approve", "Upload", ...) collide with real in-content button/heading
// text on their own step pages, so an unscoped page-wide locator is
// ambiguous. The step-check span is aria-hidden, so an unscoped
// getByRole('button', { name: 'Approve', exact: true }) would otherwise
// match this disabled nav button instead of the real per-page action.
function stepNavButton(page, label) {
  return page.locator('.wizard-progress').getByRole('button', { name: label, exact: true })
}

function stepCheck(page, label) {
  return stepNavButton(page, label).locator('.wizard-step-check')
}

// Scoped to the active step's own content area, excluding the always-
// rendered progress sidebar.
function content(page) {
  return page.locator('.wizard-content')
}

test.describe('Data Workspace Wizard (isolated database)', () => {
  test.describe.configure({ retries: 0 })

  test('full golden path: upload -> ocr -> clean -> chunk -> AI review -> approve -> build RAG', async ({
    authenticatedPage: page, state,
  }, testInfo) => {
    testInfo.setTimeout(120_000)
    const { wizard_knowledge_space_name } = state.fixtures

    await openWizard(page)

    // 1: Upload, then link the real, rights-verified data source already
    // seeded for the document-SFT closure spec (public_domain rights,
    // training_use_allowed) -- a document can't have its pages approved
    // (blocking Chunk generation) until a source is linked, and a
    // verified-rights source is what lets the AI Review Studio step below
    // exercise the real "Approve" action rather than a workaround.
    await content(page).getByLabel('PDF document').setInputFiles({
      name: 'wizard-sample.pdf', mimeType: 'application/pdf', buffer: makeRealPdfBuffer(),
    })
    await content(page).getByRole('button', { name: 'Upload securely' }).click()
    await expect(content(page).getByText(/has no linked data source yet/)).toBeVisible({ timeout: 15_000 })
    await content(page).getByLabel('Data source').selectOption({ label: 'SRC-E2E-CLOSURE-0001 -- E2E closure source' })
    await content(page).getByRole('button', { name: 'Link source' }).click()
    await expect(content(page).getByText('OCR & extraction')).toBeVisible({ timeout: 15_000 })
    await expect(stepCheck(page, 'Upload')).toHaveText('✓')

    // 2: OCR -- analyze, process, approve the first page.
    await content(page).getByRole('button', { name: 'Analyze pages' }).click()
    await expect(content(page).getByRole('button', { name: /^Process/ })).toBeEnabled({ timeout: 10_000 })
    await content(page).getByRole('button', { name: /^Process/ }).click()
    const approveButton = content(page).getByRole('button', { name: 'Approve', exact: true }).first()
    await expect(approveButton).toBeVisible({ timeout: 15_000 })
    await approveButton.click()
    await expect(content(page).getByText('Clean', { exact: true })).toBeVisible({ timeout: 10_000 })
    await expect(stepCheck(page, 'OCR')).toHaveText('✓')

    // 3: Clean -- detect repeated elements (zero or more, either way completes the step).
    await expect(content(page).getByRole('button', { name: 'Detect repeated elements' })).toBeVisible()
    await content(page).getByRole('button', { name: 'Detect repeated elements' }).click()
    await expect(content(page).getByText('Generate draft chunks from approved pages')).toBeVisible({ timeout: 10_000 })
    await expect(stepCheck(page, 'Clean')).toHaveText('✓')

    // 4: Chunk -- generate real chunks from the approved page, then
    // classify + approve one (SFT candidate generation in the next step
    // only runs from approved chunks).
    await content(page).getByRole('button', { name: 'Generate draft chunks from approved pages' }).click()
    const approveChunkButton = content(page).getByRole('button', { name: 'Classify & approve' }).first()
    await expect(approveChunkButton).toBeVisible({ timeout: 15_000 })
    await approveChunkButton.click()
    await expect(content(page).getByText('AI Review Studio', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(stepCheck(page, 'Chunk')).toHaveText('✓')

    // 5: AI Review Studio -- generate real SFT candidates, review one.
    // The linked source's rights are verified (public_domain), so the
    // real Approve action -- gated on rights_status === 'verified' -- is
    // actually reachable here, not just Needs Correction/Reject.
    await content(page).getByRole('button', { name: 'Generate SFT candidates' }).click()
    const reviewButton = content(page).getByRole('button', { name: 'Review' }).first()
    await expect(reviewButton).toBeVisible({ timeout: 15_000 })
    await reviewButton.click()
    await expect(content(page).getByRole('button', { name: 'Approve' })).toBeEnabled({ timeout: 10_000 })
    await content(page).getByRole('button', { name: 'Approve' }).click()
    await expect(content(page).getByText('Confirm and continue')).toBeVisible({ timeout: 10_000 })
    await expect(stepCheck(page, 'AI Review Studio')).toHaveText('✓')

    // 6: Approve -- confirm the batch gate.
    await content(page).getByRole('button', { name: 'Confirm and continue' }).click()
    await expect(content(page).getByRole('heading', { name: 'Build RAG', level: 3 })).toBeVisible({ timeout: 10_000 })
    await expect(stepCheck(page, 'Approve')).toHaveText('✓')

    // 7: Build RAG -- pick the real seeded knowledge space, build, verify
    // the result panel shows real IDs (checked directly against the
    // backend below, not just trusted from the UI).
    await content(page).getByLabel('Knowledge space').selectOption({ label: wizard_knowledge_space_name })
    await content(page).getByRole('button', { name: 'Build RAG' }).click()
    await expect(content(page).getByText('RAG source created and validated.')).toBeVisible({ timeout: 20_000 })
    await expect(stepCheck(page, 'Build RAG')).toHaveText('✓')

    const sourceId = await content(page).locator('.data-list article', { hasText: 'Source' }).locator('span').textContent()
    const versionId = await content(page).locator('.data-list article', { hasText: 'Version' }).locator('span').textContent()
    const chunkSetId = await content(page).locator('.data-list article', { hasText: 'Chunk set' }).locator('span').textContent()

    // Direct backend verification -- same pattern already established in
    // 06-admin-assistant.spec.js / 10-grounded-chat.spec.js: never trust a
    // UI success message alone for a real backend side effect.
    const sourceResponse = await page.evaluate(
      async ({ backendBaseUrl, sourceId }) => {
        const response = await fetch(`${backendBaseUrl}/api/admin/rag/sources/${sourceId}`, { credentials: 'include' })
        return { status: response.status, body: await response.json() }
      },
      { backendBaseUrl: state.backendBaseUrl, sourceId },
    )
    expect(sourceResponse.status).toBe(200)
    expect(sourceResponse.body.public_id).toBe(sourceId)

    const chunkSetResponse = await page.evaluate(
      async ({ backendBaseUrl, chunkSetId }) => {
        const response = await fetch(`${backendBaseUrl}/api/admin/rag/chunk-sets/${chunkSetId}`, { credentials: 'include' })
        return { status: response.status, body: await response.json() }
      },
      { backendBaseUrl: state.backendBaseUrl, chunkSetId },
    )
    expect(chunkSetResponse.status).toBe(200)
    expect(chunkSetResponse.body.status).toBe('validated')
    expect(versionId).toBeTruthy()

    // 8: "Continue in Knowledge & RAG" really navigates there, in the same
    // still-open app (no reload).
    await content(page).getByRole('button', { name: /Continue building the embedding/ }).click()
    await expect(page.getByRole('heading', { name: 'Knowledge & RAG', level: 2 })).toBeVisible()
  })

  test('progress persists across a hard refresh via sessionStorage, and the step is deep-linkable', async ({
    authenticatedPage: page,
  }) => {
    await openWizard(page)
    await content(page).getByLabel('PDF document').setInputFiles({
      name: 'wizard-refresh.pdf', mimeType: 'application/pdf', buffer: makeRealPdfBuffer(),
    })
    await content(page).getByRole('button', { name: 'Upload securely' }).click()
    await expect(content(page).getByText(/has no linked data source yet/)).toBeVisible({ timeout: 15_000 })
    await content(page).getByLabel('Data source').selectOption({ label: 'SRC-E2E-CLOSURE-0001 -- E2E closure source' })
    await content(page).getByRole('button', { name: 'Link source' }).click()
    await expect(content(page).getByText('OCR & extraction')).toBeVisible({ timeout: 15_000 })
    await expect(page).toHaveURL(/step=ocr/)

    await page.reload()
    await expect(content(page).getByText('OCR & extraction')).toBeVisible({ timeout: 10_000 })
    await expect(stepCheck(page, 'Upload')).toHaveText('✓')
  })
})
