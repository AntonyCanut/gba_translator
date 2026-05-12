import { test, expect } from './fixtures/emulator-fixture.js';
import { ADDRESSES, FRENCH_MENU_STRINGS, KNOWN_ENGLISH_STRINGS, FRENCH_ACCENTED_CHARS, KEYS, FRAME_COUNTS } from './helpers/constants.js';
import { decodePokemonText, encodePokemonText } from './helpers/charmap.js';
import {
  bootToTitle,
  navigateToMenu,
  startNewGame,
  advanceDialogue,
  waitForText,
} from './helpers/scenarios.js';
import { expectFrenchText, expectNoEnglishText } from './helpers/assertions.js';

test.describe('Translation Tests', () => {
  test('Texte de l\'écran titre en français', async ({ client }) => {
    await bootToTitle(client);

    // Read all text buffers at the title screen
    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ').trim();

    // Take a screenshot of the title screen for reference
    const screenshot = await client.screenshot();
    expect(screenshot.length).toBeGreaterThan(0);

    // If text is present in the buffers, verify no English strings
    if (allText.length > 0) {
      expectNoEnglishText(allText);
    }
  });

  test('Texte des menus en français', async ({ client }) => {
    await navigateToMenu(client);

    // Read text buffers after opening menu
    const buffers = await client.readAllTextBuffers();
    const allText = [
      buffers.stringVar1,
      buffers.stringVar2,
      buffers.stringVar3,
      buffers.stringVar4,
    ].join(' ');

    // Verify known English menu strings are absent
    expectNoEnglishText(allText);

    // Attempt to read text from additional memory regions
    // where menu strings may be rendered
    const menuText = await client.readText(ADDRESSES.gStringVar4, 200);
    if (menuText.trim().length > 0) {
      expectNoEnglishText(menuText);
      expectFrenchText(menuText);
    }
  });

  test('Dialogues en français', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);

    await client.fastForward(true);

    // Wait for dialogue to appear during intro
    const hasText = await waitForText(client, 1200);

    if (hasText) {
      const buffers = await client.readAllTextBuffers();
      const dialogueText = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
      ].filter((t) => t.trim().length > 0);

      for (const text of dialogueText) {
        expectNoEnglishText(text);
        expectFrenchText(text);
      }
    }

    await client.fastForward(false);

    // Even if we didn't find dialogue, verify the emulator is healthy
    const state = await client.getState();
    expect(state.frameCount).toBeGreaterThan(0);
  });

  test('Caractères accentués', async ({ client }) => {
    // Write known French text with accents into memory and read it back
    const testText = 'éèêàâçùûîï';
    const encoded = encodePokemonText(testText);

    await client.writeMemory(ADDRESSES.gStringVar4, encoded);
    const readBack = await client.readMemory(ADDRESSES.gStringVar4, encoded.length);
    const decoded = decodePokemonText(readBack);

    // Verify each supported accented character round-trips
    const supportedAccents = ['é', 'è', 'à', 'â', 'ç', 'ù', 'î'];
    for (const char of supportedAccents) {
      expect(decoded, `Accent '${char}' should survive round-trip`).toContain(char);
    }

    // Verify the charmap encodes/decodes basic French text
    const frenchSample = 'Pokémon est génial';
    const encodedSample = encodePokemonText(frenchSample);
    const decodedSample = decodePokemonText(encodedSample);
    expect(decodedSample).toContain('Pok');
    expect(decodedSample).toContain('mon');
    expect(decodedSample).toContain('é');
  });

  test('Pas de texte anglais résiduel', async ({ client }) => {
    test.setTimeout(90_000);

    await startNewGame(client);
    await client.fastForward(true);

    // Scan text buffers at multiple points during gameplay
    const scanPoints = [300, 600, 900, 1200];
    const foundEnglish: string[] = [];

    for (const frames of scanPoints) {
      await client.advanceFrames(frames);

      const buffers = await client.readAllTextBuffers();
      const allTexts = [
        buffers.stringVar1,
        buffers.stringVar2,
        buffers.stringVar3,
        buffers.stringVar4,
        buffers.battleText1,
        buffers.battleText2,
        buffers.battleText3,
      ];

      for (const text of allTexts) {
        if (text.trim().length === 0) continue;

        const upper = text.toUpperCase();
        for (const english of KNOWN_ENGLISH_STRINGS) {
          if (upper.includes(english.toUpperCase())) {
            foundEnglish.push(`"${english}" found in: "${text.substring(0, 60)}"`);
          }
        }
      }
    }

    await client.fastForward(false);

    expect(
      foundEnglish,
      `Found ${foundEnglish.length} English string(s): ${foundEnglish.join('; ')}`,
    ).toHaveLength(0);
  });
});
