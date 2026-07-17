import crypto from 'crypto';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { test, expect } from '@playwright/test';
import { MgbaBridgeClient } from '../../../emulator-web/src/mgba-bridge.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const ROM_PATH = path.join(PROJECT_ROOT, 'output', 'roms', 'GenedRom-fr.gba');
const SAVE_FIXTURE = path.join(
  PROJECT_ROOT,
  'tests',
  'fixtures',
  'saves',
  'party_hp_bar_fr.sav',
);
const USER_SAVE_SHA256 = '86b7d3daafa4bff101e294bd5b8c736a6004db321398e397ff1c9599127a79ac';
const KEY_PRESS_FRAMES = 4;
const INITIAL_BOOT_FRAMES = 300;
const CONTINUE_SEQUENCE_FRAMES = [60, 60, 120, 120] as const;
const MAIN_MENU_FRAMES = 60;
const MENU_CURSOR_FRAMES = 20;
const PARTY_RENDER_FRAMES = 120;

function sha256(filePath: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function screenshotBuffer(dataUrl: string): Buffer {
  return Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
}

async function startMgba(romPath: string, attempts = 3): Promise<MgbaBridgeClient> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    const client = new MgbaBridgeClient();
    try {
      await client.startMgba(romPath);
      return client;
    } catch (error) {
      lastError = error;
      await client.stop();
      if (attempt < attempts) {
        await new Promise((resolve) => setTimeout(resolve, 1_000));
      }
    }
  }

  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

test.describe('Barre de vie du menu Pokémon — sauvegarde issue #84', () => {
  test('le libellé PV laisse intact le cap gauche de la barre', async () => {
    test.setTimeout(120_000);

    expect(sha256(SAVE_FIXTURE), 'la fixture doit rester la save utilisateur exacte').toBe(
      USER_SAVE_SHA256,
    );

    const sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'party-hp-bar-fr-'));
    const isolatedRom = path.join(sandbox, 'GenedRom-fr.gba');
    const isolatedSave = path.join(sandbox, 'GenedRom-fr.sav');
    fs.copyFileSync(ROM_PATH, isolatedRom);
    fs.copyFileSync(SAVE_FIXTURE, isolatedSave);

    let client: MgbaBridgeClient | undefined;
    try {
      client = await startMgba(isolatedRom);
      await client.advanceFrames(INITIAL_BOOT_FRAMES);

      // Title → Continue → overworld, using the battery save adjacent to the ROM.
      for (const frames of CONTINUE_SEQUENCE_FRAMES) {
        await client.pressKey('A', KEY_PRESS_FRAMES);
        await client.advanceFrames(frames);
      }

      const overworld = await client.getState();
      expect(
        Number(overworld.playerX),
        'la save doit charger la position du joueur',
      ).toBeGreaterThan(0);
      expect(
        Number(overworld.playerY),
        'la save doit charger la position du joueur',
      ).toBeGreaterThan(0);

      // Main menu → Pokémon (second entry).
      await client.pressKey('START', KEY_PRESS_FRAMES);
      await client.advanceFrames(MAIN_MENU_FRAMES);
      await client.pressKey('DOWN', KEY_PRESS_FRAMES);
      await client.advanceFrames(MENU_CURSOR_FRAMES);
      await client.pressKey('A', KEY_PRESS_FRAMES);
      await client.advanceFrames(PARTY_RENDER_FRAMES);

      const screenshot = screenshotBuffer(await client.screenshot());
      expect(screenshot).toMatchSnapshot('party-hp-bar-fr.png', {
        maxDiffPixelRatio: 0,
      });
    } finally {
      await client?.stop();
      fs.rmSync(sandbox, { recursive: true, force: true });
    }

    expect(sha256(SAVE_FIXTURE), 'le test ne doit jamais modifier la save versionnée').toBe(
      USER_SAVE_SHA256,
    );
  });
});
