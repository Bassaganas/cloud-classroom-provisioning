import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: {
    timeout: 12_000
  },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: [
    {
      command: 'npm --prefix mock-server start',
      port: 3001,
      timeout: 120_000,
      reuseExistingServer: true
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      port: 5173,
      timeout: 120_000,
      reuseExistingServer: true
    }
  ]
})
