import { defineConfig } from '@playwright/test';
import path from 'path';

const projectRoot = path.resolve(import.meta.dirname, '../..');

export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 30_000,

  reporter: [
    ['list'],
    [
      path.join(projectRoot, 'tests/e2e-playwright/reporters/error-reporter.ts'),
      {
        outputDir: path.join(projectRoot, 'test-results/reports'),
        ticketsDir: path.join(projectRoot, 'tickets'),
        rom: 'frenchrom.gba',
        createTicketsEnabled: true,
      },
    ],
  ],

  use: {
    headless: true,
    screenshot: 'only-on-failure',
  },
});
