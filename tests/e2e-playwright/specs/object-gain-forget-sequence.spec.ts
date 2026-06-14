import path from 'path';
import { fileURLToPath } from 'url';
import { test, expect } from '@playwright/test';
import { MgbaBridgeClient } from '../../../emulator-web/src/mgba-bridge.js';
import { encodePokemonText, decodePokemonText } from '../helpers/charmap.js';
import { ADDRESSES } from '../helpers/constants.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const ROM_PATH = path.join(PROJECT_ROOT, 'output', 'roms', 'GenedRom-fr.gba');
const TEXT_ACTIVE_ADDR = 0x020375c0;

const STORY_PROMPT = 'Alors, prends cette CS pour aller\nle voir.';
const ITEM_GAIN_TEXT = 'BenJ a obtenu\nÉclate-Roc !';
const FORGET_PROMPT = 'Quelle capacité oublier ?';
const LEARNED_MOVE_TEXT =
  'Sabelette a bien appris la\ncapacité Éclate-Roc et oublié\nGriffe.';

async function withBridge<T>(
  romPath: string,
  fn: (client: MgbaBridgeClient) => Promise<T>,
  attempts = 3,
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    const client = new MgbaBridgeClient();
    try {
      await client.startMgba(romPath);
      return await fn(client);
    } catch (error) {
      lastError = error;
    } finally {
      await client.stop();
    }

    if (attempt < attempts) {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
    }
  }

  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

async function readStringVar4(client: MgbaBridgeClient): Promise<string> {
  const raw = await client.readMemory(ADDRESSES.gStringVar4, ADDRESSES.STRING_VAR4_SIZE);
  return decodePokemonText(raw).trim();
}

async function writeDialogue(client: MgbaBridgeClient, text: string): Promise<void> {
  await client.writeMemory(ADDRESSES.gStringVar4, encodePokemonText(text));
  await client.writeMemory(TEXT_ACTIVE_ADDR, new Uint8Array([0x01]));
  await client.advanceFrames(60);
}

test.describe('Séquence oubli / gain objet', () => {
  test('les dialogues critiques du flux restent décodés proprement', async () => {
    await withBridge(ROM_PATH, async (client) => {
      for (const page of [
        STORY_PROMPT,
        ITEM_GAIN_TEXT,
        FORGET_PROMPT,
        LEARNED_MOVE_TEXT,
      ]) {
        await writeDialogue(client, page);
        const displayed = await readStringVar4(client);
        expect(displayed).toBe(page);
        expect(displayed).not.toMatch(/[\p{L}]\?[\p{L}]/u);
      }

      await client.writeMemory(TEXT_ACTIVE_ADDR, new Uint8Array([0x00]));
      await client.advanceFrames(60);

      const state = await client.getState();
      expect(state.frameCount).toBeGreaterThan(0);
      expect(state.textActive).toBe(false);
    });
  });
});
