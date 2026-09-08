import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// System Chromium path (same pattern as apps/admin-dashboard)
const CHROMIUM_PATH = process.env.PLAYWRIGHT_CHROMIUM_PATH || '/usr/bin/chromium'

// Website E2E tests run against a production preview build (vite preview).
// No backend is required for the static public pages — the preview server
// serves the built assets and react-router-dom handles client-side routing.
// Port 5176 is chosen to avoid conflict with dev (5175) and admin-e2e (5199).
export const WEBSITE_PORT = 5176
export const WEBSITE_BASE_URL = `http://127.0.0.1:${WEBSITE_PORT}`

export default defineConfig({
  testDir: './e2e/tests',
  outputDir: './e2e/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: [['list'], ['html', { outputFolder: 'e2e/playwright-report', open: 'never' }]],
  globalSetup: './e2e/global-setup.js',
  globalTeardown: './e2e/global-teardown.js',
  use: {
    baseURL: WEBSITE_BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        launchOptions: {
          executablePath: CHROMIUM_PATH,
          args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        },
      },
    },
  ],
})
