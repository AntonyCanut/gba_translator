/**
 * Standalone Playwright config for dependency-upgrade non-regression tests.
 * Does NOT require the emulator webServer — runs pure API / type-level checks.
 */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e-playwright/specs',
  testMatch: 'deps-upgrade.spec.ts',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    headless: true,
  },
});
