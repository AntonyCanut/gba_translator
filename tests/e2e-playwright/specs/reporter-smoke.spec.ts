import { test, expect } from '@playwright/test';

test.describe('Reporter smoke tests', () => {
  test('passing test generates no error entry', async () => {
    expect(1 + 1).toBe(2);
  });

  test('failing test triggers reporter error collection', async () => {
    test.skip(!!process.env.CI, 'Intentional failure — skip in CI');
    if (process.env.SKIP_FAILURE_TEST) {
      expect(true).toBe(true);
      return;
    }
    expect('NEW GAME').toBe('NOUVELLE PARTIE');
  });
});
