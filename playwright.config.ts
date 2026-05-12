import { defineConfig } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? `http://localhost:${process.env.EMULATOR_PORT ?? '3000'}`;

export default defineConfig({
  testDir: 'tests/e2e-playwright',
  outputDir: 'test-results/screenshots',
  timeout: 120_000,
  expect: {
    timeout: 30_000,
    toMatchSnapshot: {
      maxDiffPixelRatio: 0.05,
    },
  },
  fullyParallel: false,
  workers: process.env.CI ? 1 : 2,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: [
    ['html', { outputFolder: 'test-results/reports', open: 'never' }],
    ['json', { outputFile: 'test-results/reports/results.json' }],
    ['list'],
    [
      './tests/e2e-playwright/reporters/error-reporter.ts',
      {
        outputDir: 'test-results/reports',
        ticketsDir: 'tickets',
        rom: process.env.ROM_NAME ?? 'frenchrom.gba',
        createTicketsEnabled: true,
      },
    ],
  ],
  use: {
    baseURL: BASE_URL,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    headless: true,
    viewport: { width: 480, height: 320 },
    video: 'off',
  },
  snapshotDir: 'tests/e2e-playwright/snapshots',
  snapshotPathTemplate: '{snapshotDir}/{testFileDir}/{testFileName}-snapshots/{arg}{ext}',
  projects: [
    {
      name: 'boot',
      testMatch: 'boot.spec.ts',
      use: { browserName: 'chromium' },
    },
    {
      name: 'gameplay',
      testMatch: 'gameplay.spec.ts',
      use: { browserName: 'chromium' },
    },
    {
      name: 'translation',
      testMatch: 'translation.spec.ts',
      use: { browserName: 'chromium' },
    },
    {
      name: 'visual-regression',
      testMatch: 'visual-regression.spec.ts',
      use: { browserName: 'chromium' },
    },
  ],
  webServer: {
    command: 'npx tsx src/server.ts',
    cwd: './emulator-web',
    port: parseInt(process.env.EMULATOR_PORT ?? '3000', 10),
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
