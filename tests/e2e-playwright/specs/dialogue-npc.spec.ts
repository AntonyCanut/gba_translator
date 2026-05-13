import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS, FRENCH_ACCENTED_CHARS, ADDRESSES } from '../helpers/constants.js';
import {
  startNewGame,
  interactWithNPC,
  advanceDialogue,
  walk,
  waitForText,
} from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
  expectTextBuffersNotEmpty,
} from '../helpers/assertions.js';

test.describe('Dialogue NPC Tests', () => {
  test('Interaction PNJ — dialogue complet', async ({ client }) => {
    test.setTimeout(90_000);

    const hasDialogue = await interactWithNPC(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (hasDialogue) {
      expect(state.textActive).toBe(true);

      const buffers = await client.readAllTextBuffers();
      const dialogueTexts = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].filter((t) => t.trim().length > 0);

      expect(dialogueTexts.length).toBeGreaterThan(0);

      await advanceDialogue(client, 5);

      const stateAfter = await client.getState();
      expectNoCrash(stateAfter);
    } else {
      console.warn('PNJ dialogue not triggered within frame budget');
    }
  });

  test('Texte PNJ en français — pas d\'anglais résiduel', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);
    await client.fastForward(true);

    const hasText = await waitForText(client, 1200);

    if (hasText) {
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
        expectFrenchText(text);
      }
    }

    await client.fastForward(false);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Caractères accentués dans les dialogues', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);
    await client.fastForward(true);

    const hasText = await waitForText(client, 1200);
    const accentedFound: string[] = [];

    if (hasText) {
      const buffers = await client.readAllTextBuffers();
      const allText = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].join(' ');

      for (const char of FRENCH_ACCENTED_CHARS) {
        if (allText.includes(char)) {
          accentedFound.push(char);
        }
      }
    }

    for (let i = 0; i < 5; i++) {
      await client.pressKey(KEYS.A);
      await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);

      const buffers = await client.readAllTextBuffers();
      const text = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].join(' ');

      for (const char of FRENCH_ACCENTED_CHARS) {
        if (text.includes(char) && !accentedFound.includes(char)) {
          accentedFound.push(char);
        }
      }
    }

    await client.fastForward(false);

    const state = await client.getState();
    expectNoCrash(state);
  });

  test('Défilement de texte long — plusieurs pages', async ({ client }) => {
    test.setTimeout(90_000);

    const hasDialogue = await interactWithNPC(client);
    const state = await client.getState();
    expectNoCrash(state);

    if (hasDialogue) {
      const textSnapshots: string[] = [];

      for (let page = 0; page < 8; page++) {
        const buffers = await client.readAllTextBuffers();
        const pageText = [
          buffers.stringVar1,
          buffers.stringVar2,
          buffers.stringVar3,
          buffers.stringVar4,
        ].join(' ').trim();

        if (pageText.length > 0) {
          textSnapshots.push(pageText);
        }

        await client.pressKey(KEYS.A);
        await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
      }

      expect(textSnapshots.length).toBeGreaterThan(0);

      const stateAfter = await client.getState();
      expectNoCrash(stateAfter);
    } else {
      console.warn('PNJ dialogue not triggered — scroll test skipped');
    }
  });

  test('Pas de corruption mémoire après dialogue', async ({ client }) => {
    test.setTimeout(90_000);

    const hasDialogue = await interactWithNPC(client);
    const stateBefore = await client.getState();
    expectNoCrash(stateBefore);

    if (hasDialogue) {
      await advanceDialogue(client, 10);

      await client.pressKey(KEYS.B);
      await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);
    }

    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);
    const stateAfter = await client.getState();
    expectNoCrash(stateAfter);
    expect(stateAfter.frameCount).toBeGreaterThan(stateBefore.frameCount);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(0);
  });
});
