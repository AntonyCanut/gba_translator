import fs from 'fs';
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

// Ticket "Problème pas de gain d'objet": after beating Zeph the player is
// kidnapped, escapes through a portal and a hillbilly NPC hands over the CS
// Coupe (Cut).  The game crashed at the *object gain* step.  These are the
// exact strings that script renders, with the French text the player must see.
// A crash there is a malformed string (no 0xFF terminator -> runaway text into
// script/code).  We read them straight from the built ROM so the assertion is
// deterministic and reproduces the user's path without driving the emulator
// through the unwinnable kidnapping battle.
const GIVE_CS_SEQUENCE: Array<{ offset: number; expect: string }> = [
  { offset: 0x1f33067, expect: 'portail magique' },          // hillbilly reacts to the portal
  { offset: 0x1f3316d, expect: 'prends cette CS pour aller' }, // the screenshot dialogue
  { offset: 0x1f33351, expect: 'Coupe' },                    // hands over CS Coupe / Cut
  { offset: 0x1a5df1, expect: 'a obtenu' },                  // "{PLAYER} a obtenu le {ITEM} !"
  { offset: 0x416ea4, expect: 'oublier' },                   // "Quelle capacité oublier ?"
];

function readRomString(rom: Buffer, offset: number, maxLen = 1024): { bytes: Uint8Array; terminated: boolean } {
  let end = rom.indexOf(0xff, offset);
  if (end === -1 || end - offset > maxLen) {
    return { bytes: new Uint8Array(rom.subarray(offset, offset + maxLen)), terminated: false };
  }
  return { bytes: new Uint8Array(rom.subarray(offset, end + 1)), terminated: true };
}

test.describe('Gain objet CS (séquence post-Zeph) — intégrité ROM', () => {
  test('les chaînes du don de CS sont terminées et décodent en français', () => {
    const rom = fs.readFileSync(ROM_PATH);
    for (const { offset, expect: needle } of GIVE_CS_SEQUENCE) {
      const { bytes, terminated } = readRomString(rom, offset);
      expect(terminated, `0x${offset.toString(16)}: pas de terminateur 0xFF (texte qui déborde)`).toBe(true);
      const text = decodePokemonText(bytes);
      expect(text.length, `0x${offset.toString(16)}: décodage vide`).toBeGreaterThan(0);
      expect(text, `0x${offset.toString(16)}: texte attendu manquant`).toContain(needle);
    }
  });
});

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
