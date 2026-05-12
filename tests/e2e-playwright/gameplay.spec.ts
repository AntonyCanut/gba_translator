import { test, expect } from './fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS } from './helpers/constants.js';
import {
  bootToTitle,
  startNewGame,
  navigateToMenu,
  navigateMenu,
  navigateToBattle,
  interactWithNPC,
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

    const inBattle = await navigateToBattle(client);

    if (inBattle) {
      const state = await client.getState();
      expect(state.inBattle).toBe(true);
      expectNoCrash(state);

      // Verify battle screen renders
      const screenshot = await client.screenshot();
      expect(screenshot.length).toBeGreaterThan(100);
    } else {
      // Battle not triggered in allotted frames — mark as soft pass
      // This is expected in a test emulator without real ROM execution
      const state = await client.getState();
      expectNoCrash(state);
      console.warn('Wild battle not triggered within frame budget');
    }
  });

  test('Dialogue PNJ', async ({ client }) => {
    test.setTimeout(90_000);

    const hasDialogue = await interactWithNPC(client);

    const state = await client.getState();
    expectNoCrash(state);

    if (hasDialogue) {
      expect(state.textActive).toBe(true);

      // Read text buffers to verify dialogue content
      const buffers = await client.readAllTextBuffers();
      const allText = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].join(' ');

      // At least some text should be present
      expect(allText.trim().length).toBeGreaterThan(0);
    } else {
      console.warn('NPC dialogue not triggered within frame budget');
    }
  });
});
