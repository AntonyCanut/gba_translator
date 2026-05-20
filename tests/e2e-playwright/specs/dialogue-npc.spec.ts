import { test, expect } from '../fixtures/emulator-fixture.js';
import { FRAME_COUNTS, KEYS, FRENCH_ACCENTED_CHARS } from '../helpers/constants.js';
import { advanceDialogue, setupDialogue } from '../helpers/scenarios.js';
import {
  expectNoCrash,
  expectNoEnglishText,
  expectFrenchText,
} from '../helpers/assertions.js';

test.describe('Dialogue NPC Tests', () => {
  test('Interaction PNJ — dialogue complet', async ({ client }) => {
    test.setTimeout(90_000);

    const state = await setupDialogue(client);
    expectNoCrash(state);
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
  });

  test('Texte PNJ en français — pas d\'anglais résiduel', async ({ client }) => {
    test.setTimeout(90_000);

    const state = await setupDialogue(client);
    expectNoCrash(state);
    expect(state.textActive).toBe(true);

    const buffers = await client.readAllTextBuffers();
    const allTexts = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ];

    const nonEmpty = allTexts.filter((t) => t.trim().length > 0);
    expect(nonEmpty.length).toBeGreaterThan(0);

    for (const text of nonEmpty) {
      expectNoEnglishText(text);
      expectFrenchText(text);
    }
  });

  test('Caractères accentués dans les dialogues', async ({ client }) => {
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

    const accentedFound: string[] = [];
    for (const char of FRENCH_ACCENTED_CHARS) {
      if (allText.includes(char)) {
        accentedFound.push(char);
      }
    }

    // The sample French dialogue seeded by setupDialogue contains at least
    // one accented character (apostrophes aside).
    expect(accentedFound.length).toBeGreaterThan(0);

    for (let i = 0; i < 3; i++) {
      await client.pressKey(KEYS.A);
      await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
    }

    const stateAfter = await client.getState();
    expectNoCrash(stateAfter);
  });

  test('Défilement de texte long — plusieurs pages', async ({ client }) => {
    test.setTimeout(90_000);

    const state = await setupDialogue(client);
    expectNoCrash(state);
    expect(state.textActive).toBe(true);

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
  });

  test('Pas de corruption mémoire après dialogue', async ({ client }) => {
    test.setTimeout(90_000);

    const stateBefore = await setupDialogue(client);
    expectNoCrash(stateBefore);
    expect(stateBefore.textActive).toBe(true);

    await advanceDialogue(client, 10);

    await client.pressKey(KEYS.B);
    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

    await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);
    const stateAfter = await client.getState();
    expectNoCrash(stateAfter);
    expect(stateAfter.frameCount).toBeGreaterThan(stateBefore.frameCount);

    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(0);
  });
});
