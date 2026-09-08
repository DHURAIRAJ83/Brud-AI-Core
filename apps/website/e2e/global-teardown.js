// P7-02 E2E Global Teardown — stops the vite preview server.

import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const STATE_FILE = path.join(__dirname, '.e2e-state.json')

export default async function globalTeardown() {
  if (!existsSync(STATE_FILE)) return
  try {
    const state = JSON.parse(readFileSync(STATE_FILE, 'utf-8'))
    if (state.previewPid) {
      try { process.kill(state.previewPid, 'SIGTERM') } catch { /* already gone */ }
    }
    console.log('[e2e-teardown] Preview server stopped.')
  } catch {
    // best-effort
  }
}
