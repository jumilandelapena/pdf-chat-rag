import { defineConfig, devices } from '@playwright/test'
import os from 'node:os'
import path from 'node:path'

// Against a running stack (for example docker compose): E2E_BASE_URL=http://localhost:8080
const external = process.env.E2E_BASE_URL
// Fresh backend data per run, outside the repo (and outside OneDrive on this machine)
const dataDir = process.env.E2E_DATA_DIR ?? path.join(os.tmpdir(), 'pdf-chat-rag-e2e', String(Date.now()))

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  globalTimeout: 20 * 60_000,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: external ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: external
    ? undefined
    : [
        {
          command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000',
          cwd: '../backend',
          url: 'http://127.0.0.1:8000/health',
          env: {
            LLM_PROVIDER: 'mock',
            EMBEDDINGS_PROVIDER: 'local',
            DATA_DIR: dataDir,
            CORS_ORIGINS: 'http://localhost:5173',
          },
          reuseExistingServer: !process.env.CI,
          timeout: 180_000,
        },
        {
          command: 'npm run dev',
          url: 'http://localhost:5173',
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      ],
})
