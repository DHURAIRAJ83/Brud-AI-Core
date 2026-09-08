// P7-02 E2E Global Setup
// Builds the website (vite build) and starts vite preview server.
// No backend or database required for the public website's static pages.

import { execFileSync, spawn } from 'node:child_process'
import { existsSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const WEBSITE_ROOT = path.resolve(__dirname, '..')
const STATE_FILE = path.join(__dirname, '.e2e-state.json')

export const WEBSITE_PORT = 5176
export const WEBSITE_BASE_URL = `http://127.0.0.1:${WEBSITE_PORT}`

function waitFor(url, { timeoutMs = 20000, intervalMs = 300 } = {}) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const attempt = async () => {
      try {
        const res = await fetch(url)
        if (res.ok || res.status === 404) { resolve(); return }
      } catch {
        // not yet up
      }
      if (Date.now() > deadline) {
        reject(new Error(`Timed out waiting for ${url}`))
        return
      }
      setTimeout(attempt, intervalMs)
    }
    attempt()
  })
}

export default async function globalSetup() {
  // Build the production bundle
  console.log('[e2e-setup] Building website for production…')
  execFileSync('npm', ['run', 'build'], {
    cwd: WEBSITE_ROOT,
    stdio: 'inherit',
    shell: false,
  })

  // Start vite preview server against the production build
  const viteBin = path.join(WEBSITE_ROOT, 'node_modules', '.bin', 'vite')
  const previewProcess = spawn(
    viteBin,
    ['preview', '--host', '127.0.0.1', '--port', String(WEBSITE_PORT), '--strictPort'],
    { cwd: WEBSITE_ROOT, stdio: 'ignore' },
  )

  // Wait for the preview server to be up
  await waitFor(WEBSITE_BASE_URL)
  console.log(`[e2e-setup] Preview server ready at ${WEBSITE_BASE_URL}`)

  writeFileSync(STATE_FILE, JSON.stringify({
    previewPid: previewProcess.pid,
    websiteBaseUrl: WEBSITE_BASE_URL,
  }, null, 2))
}

export { STATE_FILE }
