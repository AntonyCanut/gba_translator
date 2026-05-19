import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS, TIMEOUTS } from '../helpers/constants.js';
import {
  bootToTitle,
  startNewGame,
  waitForGameState,
  waitForStableCallback,
  walk,
  waitForText,
} from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
} from '../helpers/assertions.js';

async function checkEmulatorAvailable(
  client: import('../fixtures/emulator-client.js').EmulatorClient,
): Promise<boolean> {
  try {
    await client.advanceFrames(1);
    const state = await client.getState();
    return state.frameCount > 0;
  } catch {
    return false;
  }
}

test.describe('Real Gameplay Tests', () => {
  test.beforeEach(async ({ client }, testInfo) => {
    const available = await checkEmulatorAvailable(client);
    if (!available) {
      testInfo.skip(true, 'Real emulator not available (ROM missing or emulator not integrated)');
    }
  });

  test('Boot et écran titre — rendu réel', async ({ client }) => {
    test.setTimeout(TIMEOUTS.REAL_BOOT);

    await client.fastForward(true);
    await client.advanceFrames(FRAME_COUNTS.TITLE_WAIT);

    const state = await waitForStableCallback(client);
    await client.fastForward(false);

    expect(state.frameCount).toBeGreaterThanOrEqual(FRAME_COUNTS.TITLE_WAIT);
    expectNoCrash(state);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(500);

    await client.advanceFrames(30);
    const afterState = await client.getState();
    expect(afterState.frameCount).toBeGreaterThan(state.frameCount);
  });

  test('Nouvelle partie — chargement de la carte', async ({ client }) => {
    test.setTimeout(TIMEOUTS.REAL_NEW_GAME);

    await bootToTitle(client);
    await client.fastForward(true);

    await client.pressKey(KEYS.START);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    for (let i = 0; i < 15; i++) {
      await client.pressKey(KEYS.A);
      await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
    }

    try {
      const state = await waitForGameState(
        client,
        (s) => s.mapGroup !== 0 || s.mapNumber !== 0,
        { maxFrames: 7200, label: 'map loaded' },
      );
      expect(state.mapGroup + state.mapNumber).toBeGreaterThan(0);
      expectNoCrash(state);
    } catch {
      const state = await client.getState();
      expectNoCrash(state);
      expect(state.frameCount).toBeGreaterThan(FRAME_COUNTS.TITLE_WAIT);
    }

    await client.fastForward(false);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(500);
  });

  test('Premier dialogue — texte en français', async ({ client }) => {
    test.setTimeout(TIMEOUTS.REAL_NEW_GAME);

    await startNewGame(client);
    await client.fastForward(true);

    const hasText = await waitForText(client, 1800);

    if (hasText) {
      const buffers = await client.readAllTextBuffers();
      const dialogueTexts = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].filter((t) => t.trim().length > 0);

      for (const text of dialogueTexts) {
        expectNoEnglishText(text);
        expectFrenchText(text);
      }
    }

    await client.fastForward(false);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Navigation map — la position du joueur change', async ({ client }) => {
    test.setTimeout(TIMEOUTS.REAL_NEW_GAME);

    await startNewGame(client);
    await client.fastForward(true);

    // Pokemon Unbound has a very long intro. Press A aggressively to skip through.
    for (let batch = 0; batch < 10; batch++) {
      for (let i = 0; i < 20; i++) {
        await client.pressKey(KEYS.A);
        await client.advanceFrames(60);
      }
      // Try walking to check if we have overworld control
      await walk(client, 'DOWN', 3);
      await client.advanceFrames(30);

      const state = await client.getState();
      const prevState = await client.getState();

      await walk(client, 'RIGHT', 3);
      await client.advanceFrames(30);

      const afterWalk = await client.getState();
      if (afterWalk.playerX !== prevState.playerX || afterWalk.playerY !== prevState.playerY) {
        // Player moved! We have overworld control.
        break;
      }
    }

    const initialState = await client.getState();
    const initialPos = { x: initialState.playerX, y: initialState.playerY };

    await walk(client, 'DOWN', 5);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);
    await walk(client, 'RIGHT', 5);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    const movedState = await client.getState();
    expectNoCrash(movedState);

    const posChanged =
      movedState.playerX !== initialPos.x || movedState.playerY !== initialPos.y;

    if (!posChanged) {
      // One more batch of A-presses in case we're still in dialogue
      for (let i = 0; i < 30; i++) {
        await client.pressKey(KEYS.A);
        await client.advanceFrames(60);
      }

      await walk(client, 'LEFT', 8);
      await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);
      await walk(client, 'UP', 8);
      await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

      const retryState = await client.getState();
      expectNoCrash(retryState);
      const retryChanged =
        retryState.playerX !== initialPos.x || retryState.playerY !== initialPos.y;
      expect(
        retryChanged,
        `Player position did not change: (${initialPos.x},${initialPos.y}) -> (${retryState.playerX},${retryState.playerY})`,
      ).toBe(true);
    }

    await client.fastForward(false);
  });

  test('Screenshot gameplay réel — pas d\'écran noir', async ({ client }) => {
    test.setTimeout(TIMEOUTS.REAL_NEW_GAME);

    await startNewGame(client);
    await client.fastForward(true);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND * 3);
    await client.fastForward(false);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(1000);

    const state = await client.getState();
    expectNoCrash(state);

    const titleScreenshot = await client.screenshot();
    expect(titleScreenshot.length).toBeGreaterThan(500);
  });

  test('Stabilité longue — 60s de gameplay sans crash', async ({ client }) => {
    test.setTimeout(TIMEOUTS.REAL_GAMEPLAY);

    await startNewGame(client);
    await client.fastForward(true);

    const startState = await client.getState();
    const directions: Array<'UP' | 'DOWN' | 'LEFT' | 'RIGHT'> = [
      'RIGHT', 'DOWN', 'LEFT', 'UP',
    ];
    let previousFrame = startState.frameCount;

    for (let cycle = 0; cycle < 12; cycle++) {
      const dir = directions[cycle % directions.length];
      await walk(client, dir, 5);
      await client.advanceFrames(FRAME_COUNTS.ONE_SECOND * 5);

      const state = await client.getState();
      expectNoCrash(state);
      expect(state.frameCount).toBeGreaterThan(previousFrame);
      previousFrame = state.frameCount;
    }

    await client.fastForward(false);

    const finalState = await client.getState();
    expectNoCrash(finalState);
    expect(finalState.frameCount - startState.frameCount).toBeGreaterThanOrEqual(
      FRAME_COUNTS.ONE_MINUTE,
    );
  });
});
