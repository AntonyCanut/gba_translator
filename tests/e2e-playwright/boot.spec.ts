import { test, expect } from './fixtures/emulator-fixture.js';
import { FRAME_COUNTS } from './helpers/constants.js';
import { bootToTitle } from './helpers/scenarios.js';
import { expectNoCrash, expectFrameCountIncreasing } from './helpers/assertions.js';

test.describe('Boot Tests', () => {
  test('ROM se charge sans crash', async ({ client, page }) => {
    // Load the ROM and advance 300 frames
    await client.advanceFrames(FRAME_COUNTS.BOOT_MIN);

    const state = await client.getState();
    expect(state.frameCount).toBeGreaterThanOrEqual(FRAME_COUNTS.BOOT_MIN);

    // Take a screenshot to verify visual output
    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(0);

    // Verify no crash via page console (no unhandled errors)
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await client.advanceFrames(60);
    expect(errors).toHaveLength(0);
  });

  test('Écran titre atteint', async ({ client }) => {
    await bootToTitle(client);

    const state = await client.getState();
    expect(state.frameCount).toBeGreaterThanOrEqual(FRAME_COUNTS.TITLE_WAIT);

    // Capture title screen screenshot
    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(100);

    // Verify the emulator is responsive after reaching title
    await client.advanceFrames(30);
    const afterState = await client.getState();
    expectFrameCountIncreasing(state.frameCount, afterState.frameCount);
  });

  test('Pas de reboot dans les 60 premières secondes', async ({ client }) => {
    await client.fastForward(true);

    // Record initial state
    const initialState = await client.getState();
    const initialFrame = initialState.frameCount;
    let previousFrame = initialFrame;

    // Advance 3600 frames (60 seconds at 60fps), checking periodically
    const checkInterval = 600; // Check every 10 seconds
    const totalFrames = FRAME_COUNTS.ONE_MINUTE;

    for (let elapsed = 0; elapsed < totalFrames; elapsed += checkInterval) {
      await client.advanceFrames(checkInterval);
      const state = await client.getState();

      // Frame count must always increase
      expectFrameCountIncreasing(previousFrame, state.frameCount);
      previousFrame = state.frameCount;

      // No crash detection
      expectNoCrash(state);
    }

    await client.fastForward(false);

    const finalState = await client.getState();
    expect(finalState.frameCount - initialFrame).toBeGreaterThanOrEqual(totalFrames);
  });
});
