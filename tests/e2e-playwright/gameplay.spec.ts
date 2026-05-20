import { test, expect } from './fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS } from './helpers/constants.js';
import {
  bootToTitle,
  startNewGame,
  navigateToMenu,
  navigateMenu,
  setupInBattle,
  setupDialogue,
} from './helpers/scenarios.js';
import { expectNoCrash, expectScreenType } from './helpers/assertions.js';

test.describe('Gameplay Tests', () => {
  test('Navigation dans les menus', async ({ client }) => {
    await navigateToMenu(client);

    const stateBeforeNav = await client.getState();

    // Navigate down through menu items
    await navigateMenu(client, 'DOWN', 2);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    // Navigate back up
    await navigateMenu(client, 'UP', 2);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    // Press B to close menu
    await client.pressKey(KEYS.B);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);

    const stateAfter = await client.getState();
    expectNoCrash(stateAfter);

    // Verify frames progressed (menu was interacted with)
    expect(stateAfter.frameCount).toBeGreaterThan(stateBeforeNav.frameCount);
  });

  test('Nouveau jeu', async ({ client }) => {
    // Record state before starting new game
    const initialState = await client.getState();

    await startNewGame(client);

    const state = await client.getState();
    expectNoCrash(state);

    // Verify the game advanced significantly from the title screen
    expect(state.frameCount).toBeGreaterThan(initialState.frameCount + FRAME_COUNTS.TITLE_WAIT);

    // Take a screenshot — should show intro or gameplay, not title
    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(100);
  });

  test('Premier combat', async ({ client }) => {
    test.setTimeout(120_000);

    const state = await setupInBattle(client);
    expect(state.inBattle).toBe(true);
    expectNoCrash(state);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(100);
  });

  test('Dialogue PNJ', async ({ client }) => {
    test.setTimeout(90_000);

    const state = await setupDialogue(client);
    expectNoCrash(state);
    expect(state.textActive).toBe(true);

    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ');

    expect(allText.trim().length).toBeGreaterThan(0);
  });
});
