// Phase 15A browser-automation global teardown. Stops the isolated
// backend/frontend processes started by global-setup.js and deletes
// the temporary database/artifact directory. Never touches anything
// under the real repository's `data/` directory.

import { existsSync, readFileSync, rmSync, unlinkSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const STATE_FILE = path.join(__dirname, '.e2e-state.json')

function tryKill(pid) {
  if (!pid) return
  try {
    process.kill(pid, 'SIGTERM')
  } catch {
    // already exited
  }
}

export default async function globalTeardown() {
  if (!existsSync(STATE_FILE)) return
  const state = JSON.parse(readFileSync(STATE_FILE, 'utf-8'))

  tryKill(state.backendPid)
  tryKill(state.frontendPid)

  if (state.tempRoot && state.tempRoot.includes('brud-e2e-')) {
    rmSync(state.tempRoot, { recursive: true, force: true })
  }

  unlinkSync(STATE_FILE)
}
