import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS } from '../helpers/constants.js';
import { setupInBattle } from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
} from '../helpers/assertions.js';

test.describe('Battle Flow Tests', () => {
  test('Entrer en combat sauvage', async ({ client }) => {
    test.setTimeout(120_000);

    const state = await setupInBattle(client);
    expectNoCrash(state);
    expect(state.inBattle).toBe(true);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(100);
  });

  test('Messages de combat en français', async ({ client }) => {
    test.setTimeout(120_000);

    const state = await setupInBattle(client);
    expectNoCrash(state);
    expect(state.inBattle).toBe(true);

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
    expect(allBattleText.trim().length).toBeGreaterThan(0);
    expectFrenchText(allBattleText);
  });

  test('Noms de Pokémon et attaques visibles en combat', async ({ client }) => {
    test.setTimeout(120_000);

    const state = await setupInBattle(client);
    expectNoCrash(state);
    expect(state.inBattle).toBe(true);

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
  });

  test('Sélection d\'attaque dans le menu combat', async ({ client }) => {
    test.setTimeout(120_000);

    const state = await setupInBattle(client);
    expectNoCrash(state);
    expect(state.inBattle).toBe(true);

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
  });

  test('Stabilité post-combat — pas de reboot', async ({ client }) => {
    test.setTimeout(120_000);

    const state = await setupInBattle(client);
    expectNoCrash(state);
    expect(state.inBattle).toBe(true);

    const battleStartFrame = state.frameCount;

    for (let i = 0; i < 20; i++) {
      await client.pressKey(KEYS.A);
      await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
    }

    await client.advanceFrames(FRAME_COUNTS.TEN_SECONDS);

    const stateAfter = await client.getState();
    expectNoCrash(stateAfter);
    expect(stateAfter.frameCount).toBeGreaterThan(battleStartFrame);
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
