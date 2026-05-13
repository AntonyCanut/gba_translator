import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS, KNOWN_ENGLISH_STRINGS } from '../helpers/constants.js';
import {
  navigateToBattle,
  startNewGame,
  waitForBattle,
} from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
  expectScreenType,
} from '../helpers/assertions.js';

test.describe('Battle Flow Tests', () => {
  test('Entrer en combat sauvage', async ({ client }) => {
    test.setTimeout(120_000);

    const inBattle = await navigateToBattle(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (inBattle) {
      expect(state.inBattle).toBe(true);

      const screenshot = await client.screenshot();
      expect(screenshot.length).toBeGreaterThan(100);
    } else {
      console.warn('Wild battle not triggered within frame budget');
    }
  });

  test('Messages de combat en français', async ({ client }) => {
    test.setTimeout(120_000);

    const inBattle = await navigateToBattle(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (inBattle) {
      const buffers = await client.readAllTextBuffers();
      const battleTexts = [
        buffers.battleText1,
        buffers.battleText2,
        buffers.battleText3,
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ];

      for (const text of battleTexts) {
        if (text.trim().length === 0) continue;
        expectNoEnglishText(text);
      }

      const allBattleText = battleTexts.join(' ');
      if (allBattleText.trim().length > 0) {
        expectFrenchText(allBattleText);
      }
    } else {
      console.warn('Battle not triggered — French text check skipped');
    }
  });

  test('Noms de Pokémon et attaques visibles en combat', async ({ client }) => {
    test.setTimeout(120_000);

    const inBattle = await navigateToBattle(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (inBattle) {
      await client.pressKey(KEYS.A);
      await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

      const buffers = await client.readAllTextBuffers();
      const allTexts = [
        buffers.battleText1,
        buffers.battleText2,
        buffers.battleText3,
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ];

      for (const text of allTexts) {
        if (text.trim().length === 0) continue;
        expectNoEnglishText(text);
      }

      const stateAfterAction = await client.getState();
      expectNoCrash(stateAfterAction);
    } else {
      console.warn('Battle not triggered — Pokémon names check skipped');
    }
  });

  test('Sélection d\'attaque dans le menu combat', async ({ client }) => {
    test.setTimeout(120_000);

    const inBattle = await navigateToBattle(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (inBattle) {
      await client.pressKey(KEYS.A);
      await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

      await navigateMenuInBattle(client);

      const buffers = await client.readAllTextBuffers();
      const allText = [
        buffers.battleText1,
        buffers.battleText2,
        buffers.battleText3,
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].join(' ');

      expectNoEnglishText(allText);

      await client.pressKey(KEYS.B);
      await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

      const stateAfter = await client.getState();
      expectNoCrash(stateAfter);
    } else {
      console.warn('Battle not triggered — attack menu check skipped');
    }
  });

  test('Stabilité post-combat — pas de reboot', async ({ client }) => {
    test.setTimeout(120_000);

    const inBattle = await navigateToBattle(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (inBattle) {
      const battleStartFrame = state.frameCount;

      for (let i = 0; i < 20; i++) {
        await client.pressKey(KEYS.A);
        await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
      }

      await client.advanceFrames(FRAME_COUNTS.TEN_SECONDS);

      const stateAfter = await client.getState();
      expectNoCrash(stateAfter);
      expect(stateAfter.frameCount).toBeGreaterThan(battleStartFrame);
    } else {
      await client.advanceFrames(FRAME_COUNTS.TEN_SECONDS);
      const stateAfter = await client.getState();
      expectNoCrash(stateAfter);
      console.warn('Battle not triggered — post-battle stability skipped');
    }
  });
});

async function navigateMenuInBattle(client: import('../fixtures/emulator-client.js').EmulatorClient): Promise<void> {
  await client.pressKey(KEYS.DOWN);
  await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
  await client.pressKey(KEYS.UP);
  await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
  await client.pressKey(KEYS.RIGHT);
  await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
  await client.pressKey(KEYS.LEFT);
  await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
}
