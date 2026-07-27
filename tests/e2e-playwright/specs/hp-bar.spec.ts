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
 *
 * Two more holes are closed here, because pixel parity alone cannot see them:
 *
 * * a capture that never reached the page would be blank, and a blank region
 *   equals a blank region — so each bar must hold several distinct colours
 *   before any parity claim counts;
 * * the label letters are excluded from the parity regions (they legitimately
 *   differ per language), so a build shipping the English sheet wholesale —
 *   correct bar, untranslated « HP » — would pass everything. The label region
 *   must therefore differ from the English capture.
 *
 * Every build is driven through mGBA exactly once; all its assertions share
 * that capture.
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
  HP_LABEL_REGION,
  PAGE_ANCHOR_REGIONS,
  PARTY_HP_BAR_REGIONS,
  describeRegion,
  distinctColours,
  readScreen,
  regionDiffCount,
  regionsMatchAll,
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

/**
 * Piloter mGBA jusqu'à la page Capacités coûte plusieurs minutes par ROM, donc
 * chaque build n'est capturé qu'une fois : les cas qui suivent lisent tous la
 * même paire de framebuffers. Le describe est `serial`, donc l'ordre et le
 * partage d'état sont garantis.
 */
const captures = new Map<string, Capture>();

async function captureOnce(code: string): Promise<Capture> {
  const cached = captures.get(code);
  if (cached) {
    return cached;
  }
  const capture = await captureHpBars(romFor(code), code);
  captures.set(code, capture);
  return capture;
}

/** Nombre minimal de couleurs attendu dans une barre réellement dessinée. */
const MIN_BAR_COLOURS = 3;
const MIN_PARTY_BAR_COLOURS = 2;

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

  test('la capture anglaise de référence montre de vraies barres', () => {
    // Deux écrans noirs sont pixel-identiques : sans ce garde-fou, toutes les
    // comparaisons de parité pourraient passer sur des captures vides.
    expect(
      distinctColours(english.skills, HP_BAR_REGION),
      `la barre du résumé anglaise doit être dessinée :\n`
      + describeRegion(english.skills, HP_BAR_REGION),
    ).toBeGreaterThanOrEqual(MIN_BAR_COLOURS);
    PARTY_HP_BAR_REGIONS.forEach((region, slot) => {
      expect(
        distinctColours(english.party, region),
        `la barre anglaise de l'emplacement ${slot + 1} doit être dessinée :\n`
        + describeRegion(english.party, region),
      ).toBeGreaterThanOrEqual(MIN_PARTY_BAR_COLOURS);
    });
  });

  for (const build of BUILDS) {
    test(`les barres de vie ${build.label} sont identiques aux barres anglaises`, async () => {
      test.setTimeout(400_000);
      const translated = await captureOnce(build.code);

      // The Skills page was located by the DEFENSE and EXP. labels, the only
      // two that stay identical in every build, so they must match in both
      // runs — that is what proves both ROMs are on the same page before
      // anything is asserted about the bar.
      expect(
        regionsMatchAll(translated.skills, english.skills, PAGE_ANCHOR_REGIONS),
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

    test(`le libellé de la barre ${build.label} est bien traduit`, async () => {
      test.setTimeout(400_000);
      const translated = await captureOnce(build.code);

      // Les lettres sont volontairement hors des comparaisons de parité : une
      // ROM qui embarquerait la planche anglaise entière — barre intacte mais
      // libellé « HP » — passerait tous les autres contrôles.
      expect(
        regionDiffCount(translated.skills, english.skills, HP_LABEL_REGION),
        `le libellé ${build.label} est resté « HP » :\n`
        + `${build.code.toUpperCase()}:\n${describeRegion(translated.skills, HP_LABEL_REGION)}`,
      ).toBeGreaterThan(0);

      // …et le repeindre ne doit jamais déborder sur la barre elle-même.
      expect(
        regionDiffCount(translated.skills, english.skills, HP_BAR_REGION),
        'le tracé du libellé a mordu sur la barre',
      ).toBe(0);
    });

    test(`les barres capturées sur la ROM ${build.label} sont bien dessinées`, async () => {
      test.setTimeout(400_000);
      const translated = await captureOnce(build.code);

      expect(
        distinctColours(translated.skills, HP_BAR_REGION),
        `barre du résumé ${build.label} vide ou uniforme :\n`
        + describeRegion(translated.skills, HP_BAR_REGION),
      ).toBeGreaterThanOrEqual(MIN_BAR_COLOURS);
      PARTY_HP_BAR_REGIONS.forEach((region, slot) => {
        expect(
          distinctColours(translated.party, region),
          `barre ${build.label} de l'emplacement ${slot + 1} vide ou uniforme :\n`
          + describeRegion(translated.party, region),
        ).toBeGreaterThanOrEqual(MIN_PARTY_BAR_COLOURS);
      });
    });

    test(`le test détecte des barres abîmées sur la ROM ${build.label}`, async () => {
      test.setTimeout(400_000);
      const regressed = await captureHpBars(romFor(build.code), `${build.code}-regressed`, true);

      // The recognition anchor must survive the damage: only the bars change.
      expect(
        regionsMatchAll(regressed.skills, english.skills, PAGE_ANCHOR_REGIONS),
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
