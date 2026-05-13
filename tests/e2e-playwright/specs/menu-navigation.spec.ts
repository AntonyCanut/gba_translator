import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS, FRENCH_MENU_STRINGS } from '../helpers/constants.js';
import {
  navigateToMenu,
  navigateMenu,
  bootToTitle,
} from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
} from '../helpers/assertions.js';

test.describe('Menu Navigation Tests', () => {
  test('Labels du menu principal en français', async ({ client }) => {
    await navigateToMenu(client);

    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ');

    expectNoEnglishText(allText);

    if (allText.trim().length > 0) {
      expectFrenchText(allText);
    }

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Navigation Pokédex, Pokémon, Sac via les flèches', async ({ client }) => {
    await navigateToMenu(client);

    await navigateMenu(client, 'DOWN', 3);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    const midBuffers = await client.readAllTextBuffers();
    const midText = [
      midBuffers.stringVar1,
      midBuffers.stringVar2,
      midBuffers.stringVar3,
      midBuffers.stringVar4,
    ].join(' ');
    expectNoEnglishText(midText);

    await navigateMenu(client, 'UP', 3);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Sous-menu Options accessible', async ({ client }) => {
    await navigateToMenu(client);

    await navigateMenu(client, 'DOWN', 5);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ');
    expectNoEnglishText(allText);

    await client.pressKey(KEYS.B);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Sauvegarde accessible depuis le menu', async ({ client }) => {
    await navigateToMenu(client);

    await navigateMenu(client, 'DOWN', 4);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ');
    expectNoEnglishText(allText);

    await client.pressKey(KEYS.B);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Pas de crash après 10 transitions de menu', async ({ client }) => {
    await navigateToMenu(client);

    for (let i = 0; i < 10; i++) {
      await navigateMenu(client, 'DOWN', 1);
      await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

      if (i % 3 === 0) {
        await client.pressKey(KEYS.A);
        await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
        await client.pressKey(KEYS.B);
        await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
      }
    }

    await client.pressKey(KEYS.B);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    const state = await client.getState();
    expectNoCrash(state);
    expect(state.frameCount).toBeGreaterThan(0);
  });
});
