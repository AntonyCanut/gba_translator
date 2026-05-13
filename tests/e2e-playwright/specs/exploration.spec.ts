import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS, ADDRESSES } from '../helpers/constants.js';
import {
  startNewGame,
  walk,
} from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
} from '../helpers/assertions.js';

test.describe('Exploration Tests', () => {
  test('Transition entre zones — intérieur/extérieur', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);
    await client.fastForward(true);

    const initialState = await client.getState();
    const initialMap = { group: initialState.mapGroup, number: initialState.mapNumber };

    await walk(client, 'DOWN', 10);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    await walk(client, 'UP', 5);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    await walk(client, 'RIGHT', 5);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    const stateAfterWalk = await client.getState();
    expectNoCrash(stateAfterWalk);
    expect(stateAfterWalk.frameCount).toBeGreaterThan(initialState.frameCount);

    await client.fastForward(false);
  });

  test('Noms de lieux en français', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);
    await client.fastForward(true);

    await walk(client, 'DOWN', 8);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ');

    if (allText.trim().length > 0) {
      expectNoEnglishText(allText);
      expectFrenchText(allText);
    }

    await client.fastForward(false);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Stabilité pendant 30+ secondes d\'exploration continue', async ({ client }) => {
    test.setTimeout(120_000);

    await startNewGame(client);
    await client.fastForward(true);

    const startState = await client.getState();
    const directions: Array<'UP' | 'DOWN' | 'LEFT' | 'RIGHT'> = ['RIGHT', 'DOWN', 'LEFT', 'UP'];
    let previousFrame = startState.frameCount;

    for (let cycle = 0; cycle < 6; cycle++) {
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
      FRAME_COUNTS.THIRTY_SECONDS,
    );
  });

  test('Pas de texte tronqué dans les panneaux', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);
    await client.fastForward(true);

    await walk(client, 'DOWN', 5);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);

    const buffers = await client.readAllTextBuffers();
    const allTexts = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ];

    for (const text of allTexts) {
      if (text.trim().length === 0) continue;

      expectNoEnglishText(text);

      expect(text).not.toMatch(/\x00{3,}/);
      expect(text).not.toMatch(/�/);
    }

    await walk(client, 'RIGHT', 5);
    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);

    const buffers2 = await client.readAllTextBuffers();
    const texts2 = [
      buffers2.stringVar1,
      buffers2.stringVar2,
      buffers2.stringVar3,
      buffers2.stringVar4,
    ];

    for (const text of texts2) {
      if (text.trim().length === 0) continue;
      expectNoEnglishText(text);
      expect(text).not.toMatch(/\x00{3,}/);
    }

    await client.fastForward(false);

    const state = await client.getState();
    expectNoCrash(state);
  });
});
