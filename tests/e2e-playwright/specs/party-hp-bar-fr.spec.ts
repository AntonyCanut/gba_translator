import crypto from 'crypto';
import { execFile } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { promisify } from 'util';
import { fileURLToPath } from 'url';
import { test, expect } from '@playwright/test';

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
const TSX_PATH = path.join(PROJECT_ROOT, 'emulator-web', 'node_modules', '.bin', 'tsx');
const PROBE_PATH = path.join(PROJECT_ROOT, 'tests', 'e2e-playwright', 'helpers', 'party-hp-bar-probe.ts');
const execFileAsync = promisify(execFile);

function sha256(filePath: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

test.describe('Barre de vie du menu Pokémon — sauvegarde issue #84', () => {
  test('le libellé PV laisse intact le cap gauche de la barre', async () => {
    test.setTimeout(240_000);

    expect(sha256(SAVE_FIXTURE), 'la fixture doit rester la save utilisateur exacte').toBe(
      USER_SAVE_SHA256,
    );

    const sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'party-hp-bar-fr-'));
    const isolatedRom = path.join(sandbox, 'GenedRom-fr.gba');
    const isolatedSave = path.join(sandbox, 'GenedRom-fr.sav');
    const screenshotPath = path.join(sandbox, 'party-hp-bar-fr.png');
    fs.copyFileSync(ROM_PATH, isolatedRom);
    fs.copyFileSync(SAVE_FIXTURE, isolatedSave);

    let screenshot: Buffer;
    try {
      const { stdout } = await execFileAsync(TSX_PATH, [
        PROBE_PATH,
        isolatedRom,
        screenshotPath,
      ], {
        cwd: PROJECT_ROOT,
        env: process.env,
        encoding: 'utf8',
        timeout: 220_000,
      });
      const state = JSON.parse(stdout.trim().split('\n').at(-1) ?? '{}') as {
        playerX?: number;
        playerY?: number;
      };
      expect(state.playerX, 'la save doit charger la position du joueur').toBeGreaterThan(0);
      expect(state.playerY, 'la save doit charger la position du joueur').toBeGreaterThan(0);
      screenshot = fs.readFileSync(screenshotPath);
    } finally {
      fs.rmSync(sandbox, { recursive: true, force: true });
    }

    expect(screenshot).toMatchSnapshot('party-hp-bar-fr.png', {
      maxDiffPixelRatio: 0,
    });
    expect(sha256(SAVE_FIXTURE), 'le test ne doit jamais modifier la save versionnée').toBe(
      USER_SAVE_SHA256,
    );
  });
});
