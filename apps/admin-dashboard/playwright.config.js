import { defineConfig, devices } from '@playwright/test'

// This sandboxed environment's headless Chromium hangs on the default
// /dev/shm size; --disable-dev-shm-usage fixes it (verified directly --
// see docs/production/phase15a_production_verification_plan.md §0).
// --no-sandbox is required because this container has no user namespace
// isolation available to Chromium's own sandbox.
const CHROMIUM_PATH = process.env.PLAYWRIGHT_CHROMIUM_PATH || '/usr/bin/chromium'

export default defineConfig({
  testDir: './e2e/tests',
  outputDir: './e2e/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  globalSetup: './e2e/global-setup.js',
  globalTeardown: './e2e/global-teardown.js',
  use: {
    baseURL: 'http://127.0.0.1:5199',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          executablePath: CHROMIUM_PATH,
          args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        },
      },
    },
  ],
})
