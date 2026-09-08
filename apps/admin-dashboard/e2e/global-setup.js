// Phase 15A browser-automation global setup.
//
// Spins up a real backend (uvicorn) and a real frontend (vite dev
// server) against a brand-new, isolated temporary SQLite database --
// never the real development database. Seeds that database through
// `seed.py`, which reuses the exact same repository/service APIs the
// Python test suite already relies on. Writes connection info + every
// seeded fixture's public_id to `.e2e-state.json` so the tests (and
// `global-teardown.js`) can read it back.

import { execFileSync, spawn } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..')
const ADMIN_DASHBOARD_ROOT = path.resolve(__dirname, '..')
const STATE_FILE = path.join(__dirname, '.e2e-state.json')

export const BACKEND_PORT = 8199
export const FRONTEND_PORT = 5199
export const BACKEND_BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`
export const FRONTEND_BASE_URL = `http://127.0.0.1:${FRONTEND_PORT}`

function pythonExecutable() {
  const venvPython = path.join(REPO_ROOT, 'venv', 'bin', 'python')
  return existsSync(venvPython) ? venvPython : 'python3'
}

function waitForHealthy(url, { timeoutMs = 30000, intervalMs = 300 } = {}) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const attempt = async () => {
      try {
        const response = await fetch(url)
        if (response.ok) {
          resolve()
          return
        }
      } catch {
        // not up yet
      }
      if (Date.now() > deadline) {
        reject(new Error(`timed out waiting for ${url} to become healthy`))
        return
      }
      setTimeout(attempt, intervalMs)
    }
    attempt()
  })
}

export default async function globalSetup() {
  const tempRoot = mkdtempSync(path.join(tmpdir(), 'brud-e2e-'))
  const paths = {
    database: path.join(tempRoot, 'db.sqlite'),
    backups: path.join(tempRoot, 'backups'),
    pretraining: path.join(tempRoot, 'pretraining'),
    tokenizerCorpus: path.join(tempRoot, 'tokenizer_corpus'),
    tokenizers: path.join(tempRoot, 'tokenizers'),
    coreModels: path.join(tempRoot, 'core_models'),
    coreCheckpoints: path.join(tempRoot, 'core_checkpoints'),
    releaseArtifacts: path.join(tempRoot, 'release_artifacts'),
    releaseBundles: path.join(tempRoot, 'release_bundles'),
    allowedData: tempRoot,
  }

  const python = pythonExecutable()
  const seedOutput = execFileSync(
    python,
    [
      path.join(__dirname, 'seed.py'),
      '--database-path', paths.database,
      '--backup-dir', paths.backups,
      '--pretraining-dir', paths.pretraining,
      '--tokenizer-corpus-dir', paths.tokenizerCorpus,
      '--tokenizer-dir', paths.tokenizers,
      '--core-model-dir', paths.coreModels,
      '--core-checkpoint-dir', paths.coreCheckpoints,
      '--release-artifact-dir', paths.releaseArtifacts,
      '--release-bundle-dir', paths.releaseBundles,
      '--allowed-data-dir', paths.allowedData,
    ],
    { cwd: REPO_ROOT, encoding: 'utf-8' },
  )
  const lastLine = seedOutput.trim().split('\n').pop()
  const fixtures = JSON.parse(lastLine)

  const backendEnv = {
    ...process.env,
    BRUD_ENV: 'development',
    BRUD_HOST: '127.0.0.1',
    BRUD_PORT: String(BACKEND_PORT),
    BRUD_DATABASE_PATH: paths.database,
    BRUD_DATABASE_BACKUP_DIR: paths.backups,
    BRUD_ALLOWED_DATA_DIR: paths.allowedData,
    BRUD_PRETRAINING_DIR: paths.pretraining,
    BRUD_TOKENIZER_CORPUS_DIR: paths.tokenizerCorpus,
    BRUD_TOKENIZER_DIR: paths.tokenizers,
    BRUD_CORE_MODEL_DIR: paths.coreModels,
    BRUD_CORE_CHECKPOINT_DIR: paths.coreCheckpoints,
    BRUD_RELEASE_ARTIFACT_DIR: paths.releaseArtifacts,
    BRUD_RELEASE_BUNDLE_DIR: paths.releaseBundles,
    BRUD_ALLOW_EXTERNAL_STORAGE: 'true',
    BRUD_ADMIN_ORIGIN: FRONTEND_BASE_URL,
    BRUD_CHATBOT_ORIGIN: FRONTEND_BASE_URL,
    BRUD_LOG_LEVEL: 'WARNING',
    // The real global per-IP rate limiter (backend/core/rate_limit_middleware.py,
    // default 120 req/60s) is a production safety net, not something this
    // suite should silently weaken -- but every Playwright test shares one
    // client IP (127.0.0.1) against one long-lived backend process, and a
    // single realistic multi-step admin workflow (e.g. the Core Model
    // lifecycle spec's several tab loads, each firing a handful of parallel
    // GETs) can legitimately exceed that budget well before a real,
    // human-paced admin session would. Raised for this isolated e2e process
    // only; production defaults in backend/core/config.py are untouched.
    BRUD_HTTP_RATE_LIMIT_MAX_REQUESTS: '5000',
  }
  const backendProcess = spawn(
    python,
    ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    { cwd: REPO_ROOT, env: backendEnv, stdio: 'ignore' },
  )

  const frontendEnv = {
    ...process.env,
    VITE_API_BASE_URL: BACKEND_BASE_URL,
  }
  // Invoke the vite binary directly (not via `npx vite`) -- `npx` spawns
  // an intermediate wrapper process, so killing *its* pid in
  // global-teardown.js leaves the real vite child running behind.
  const viteBin = path.join(ADMIN_DASHBOARD_ROOT, 'node_modules', '.bin', 'vite')
  const frontendProcess = spawn(
    viteBin,
    ['--host', '127.0.0.1', '--port', String(FRONTEND_PORT), '--strictPort'],
    { cwd: ADMIN_DASHBOARD_ROOT, env: frontendEnv, stdio: 'ignore' },
  )

  await waitForHealthy(`${BACKEND_BASE_URL}/api/health`)
  await waitForHealthy(FRONTEND_BASE_URL)

  writeFileSync(
    STATE_FILE,
    JSON.stringify(
      {
        tempRoot,
        backendPid: backendProcess.pid,
        frontendPid: frontendProcess.pid,
        backendBaseUrl: BACKEND_BASE_URL,
        frontendBaseUrl: FRONTEND_BASE_URL,
        fixtures,
      },
      null,
      2,
    ),
  )
}

export function readE2eState() {
  return JSON.parse(readFileSync(STATE_FILE, 'utf-8'))
}

export { STATE_FILE }
