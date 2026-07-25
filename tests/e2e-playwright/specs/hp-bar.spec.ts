/**
 * GitHub issue #84 — « la barre de vie est tronquée sur les deux extrémités »
 * on the second tab of a Pokémon's status.
 *
 * Two screens draw an HP bar from a tile sheet a label redraw can damage: the
 * party menu (LZ77 0x008001D0) and the summary Skills page (LZ77 0x00E9B4B8).
 * Both bars are pure graphics that no translation should ever change, so the
 * reference is not a golden captured from a translated build — that would only
 * prove the build reproduces itself, and it is how this regression survived two
 * green test runs. The reference is the *English* ROM, driven through the very
 * same navigation with the very same save; every translated build must be
 * pixel-identical to it, label letters excluded.
 *
 * The three builds share the defect and the fix — `repair_localized_lz77_blocks`
 * copies the capless Spanish sheet into all of them — so all three are checked.
 * For each, a second test damages a throwaway copy (Spanish sheet back on the
 * summary, bar cap blanked on the party menu) and requires the assertions to
 * fail; without it the parity tests could pass by construction.
 */

import crypto from 'crypto';
import { execFile } from 'child_process';
import fs from 'fs';
import path from 'path';
import { promisify } from 'util';
import { fileURLToPath } from 'url';
import { PNG } from 'pngjs';
import { test, expect } from '@playwright/test';
import {
  HP_BAR_REGION,
  PARTY_HP_BAR_REGIONS,
  STAT_LABELS_REGION,
  describeRegion,
  readScreen,
  regionDiffCount,
  regionsMatch,
  partyScreenshotPath,
} from '../helpers/hp-bar-regions.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const EN_ROM = path.join(PROJECT_ROOT, 'input', 'roms', 'englishrom.gba');
const SAVE_FIXTURE = path.join(
  PROJECT_ROOT, 'tests', 'fixtures', 'saves', 'party_hp_bar_fr.sav',
);
const USER_SAVE_SHA256 = '86b7d3daafa4bff101e294bd5b8c736a6004db321398e397ff1c9599127a79ac';
const TSX_PATH = path.join(PROJECT_ROOT, 'emulator-web', 'node_modules', '.bin', 'tsx');
const PROBE_PATH = path.join(
  PROJECT_ROOT, 'tests', 'e2e-playwright', 'helpers', 'hp-bar-probe.ts',
);
const ANCHOR_PATH = path.join(
  PROJECT_ROOT, 'tests', 'e2e-playwright', 'snapshots', 'specs',
  'hp-bar.spec.ts-snapshots', 'summary-stat-labels-anchor.png',
);
const REGRESS_SCRIPT = path.join(PROJECT_ROOT, 'scripts', 'regress_summary_hp_bar.py');
const execFileAsync = promisify(execFile);

/**
 * The German and Italian ROMs are build artefacts (gitignored), so a missing
 * one is a "you forgot to build" error, never a silent skip.
 */
const BUILDS = [
  { code: 'fr', label: 'française', make: 'make build-fr' },
  { code: 'de', label: 'allemande', make: 'make build-de' },
  { code: 'it', label: 'italienne', make: 'make build-it' },
] as const;

function romFor(code: string): string {
  return path.join(PROJECT_ROOT, 'output', 'roms', `GenedRom-${code}.gba`);
}

function sha256(filePath: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

interface Capture {
  skills: PNG;
  party: PNG;
  searchedMenuEntries: number;
}

/**
 * Copy *sourceRom* and the user save into their own sandbox, optionally damage
 * the copy, then drive it to the party menu and the Skills page and read both
 * framebuffers back.
 */
async function captureHpBars(sourceRom: string, label: string,
                             regress = false): Promise<Capture> {
  const sandbox = fs.mkdtempSync(path.join(PROJECT_ROOT, 'output', `hp-bar-${label}-`));
  const romName = path.basename(sourceRom, '.gba');
  const isolatedRom = path.join(sandbox, `${romName}.gba`);
  const isolatedSave = path.join(sandbox, `${romName}.sav`);
  const screenshotPath = path.join(sandbox, 'hp-bar.png');
  fs.copyFileSync(sourceRom, isolatedRom);
  fs.copyFileSync(SAVE_FIXTURE, isolatedSave);

  try {
    if (regress) {
      await execFileAsync('python3', [REGRESS_SCRIPT, '--rom', isolatedRom], {
        cwd: PROJECT_ROOT,
        encoding: 'utf8',
      });
    }

    const { stdout } = await execFileAsync(
      TSX_PATH,
      [PROBE_PATH, isolatedRom, screenshotPath, ANCHOR_PATH],
      { cwd: PROJECT_ROOT, env: process.env, encoding: 'utf8', timeout: 300_000 },
    );
    const state = JSON.parse(stdout.trim().split('\n').at(-1) ?? '{}') as {
      playerX?: number;
      playerY?: number;
      searchedMenuEntries?: number;
    };
    expect(state.playerX, `${label}: la save doit charger le joueur`).toBeGreaterThan(0);
    expect(state.playerY, `${label}: la save doit charger le joueur`).toBeGreaterThan(0);

    return {
      skills: readScreen(screenshotPath),
      party: readScreen(partyScreenshotPath(screenshotPath)),
      searchedMenuEntries: state.searchedMenuEntries ?? 0,
    };
  } finally {
    fs.rmSync(sandbox, { recursive: true, force: true });
  }
}

test.describe('Barres de vie — issue #84', () => {
  test.describe.configure({ mode: 'serial' });

  let english: Capture;

  test.beforeAll(async () => {
    test.setTimeout(600_000);
    expect(sha256(SAVE_FIXTURE), 'la fixture doit rester la save utilisateur exacte')
      .toBe(USER_SAVE_SHA256);
    for (const build of BUILDS) {
      expect(
        fs.existsSync(romFor(build.code)),
        `ROM ${build.label} absente — lancer \`${build.make}\``,
      ).toBe(true);
    }
    english = await captureHpBars(EN_ROM, 'en');
  });

  test.afterAll(() => {
    expect(sha256(SAVE_FIXTURE), 'le test ne doit jamais modifier la save versionnée')
      .toBe(USER_SAVE_SHA256);
  });

  for (const build of BUILDS) {
    test(`les barres de vie ${build.label} sont identiques aux barres anglaises`, async () => {
      test.setTimeout(400_000);
      const translated = await captureHpBars(romFor(build.code), build.code);

      // The Skills page was located by the stat-label column, so it must be
      // identical in both runs — that is what proves both ROMs are on the same
      // page before anything is asserted about the bar.
      expect(
        regionsMatch(translated.skills, english.skills, STAT_LABELS_REGION),
        `la ROM ${build.label} doit être sur la page Capacités`,
      ).toBe(true);
      expect(
        translated.searchedMenuEntries,
        'le probe doit retrouver la page en inspectant les entrées du menu',
      ).toBeGreaterThan(0);

      expect(
        regionDiffCount(translated.skills, english.skills, HP_BAR_REGION),
        `barre du résumé ${build.label} ≠ anglaise (caps compris) :\n`
        + `${build.code.toUpperCase()}:\n${describeRegion(translated.skills, HP_BAR_REGION)}\n`
        + `EN:\n${describeRegion(english.skills, HP_BAR_REGION)}`,
      ).toBe(0);

      PARTY_HP_BAR_REGIONS.forEach((region, slot) => {
        expect(
          regionDiffCount(translated.party, english.party, region),
          `barre du menu Pokémon ${build.label}, emplacement ${slot + 1} ≠ anglaise :\n`
          + `${build.code.toUpperCase()}:\n${describeRegion(translated.party, region)}\n`
          + `EN:\n${describeRegion(english.party, region)}`,
        ).toBe(0);
      });
    });

    test(`le test détecte des barres abîmées sur la ROM ${build.label}`, async () => {
      test.setTimeout(400_000);
      const regressed = await captureHpBars(romFor(build.code), `${build.code}-regressed`, true);

      // The recognition anchor must survive the damage: only the bars change.
      expect(
        regionsMatch(regressed.skills, english.skills, STAT_LABELS_REGION),
        `la ROM ${build.label} régressée doit atteindre la même page`,
      ).toBe(true);
      expect(
        regionDiffCount(regressed.skills, english.skills, HP_BAR_REGION),
        'la barre du résumé sans extrémités doit être vue comme différente',
      ).toBeGreaterThan(0);
      expect(
        PARTY_HP_BAR_REGIONS.every(
          (region) => regionDiffCount(regressed.party, english.party, region) > 0,
        ),
        'le cap effacé du menu Pokémon doit être vu comme différent',
      ).toBe(true);
    });
  }
});
