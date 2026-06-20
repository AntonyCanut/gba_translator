import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { test, expect } from '@playwright/test';
import { decodePokemonText } from '../helpers/charmap.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const ROM_PATH = path.join(PROJECT_ROOT, 'output', 'roms', 'GenedRom-fr.gba');

// GBA ROM base address — subtract from any pointer to get ROM file offset.
const GBA_ROM_BASE = 0x08000000;

function readRomString(
  rom: Buffer,
  offset: number,
  maxLen = 256,
): { text: string; terminated: boolean } {
  const end = rom.indexOf(0xff, offset);
  if (end === -1 || end - offset > maxLen) {
    const bytes = new Uint8Array(rom.subarray(offset, offset + maxLen));
    return { text: decodePokemonText(bytes), terminated: false };
  }
  const bytes = new Uint8Array(rom.subarray(offset, end + 1));
  return { text: decodePokemonText(bytes), terminated: true };
}

function readPointer(rom: Buffer, offset: number): number {
  const ptr =
    rom[offset] |
    (rom[offset + 1] << 8) |
    (rom[offset + 2] << 16) |
    (rom[offset + 3] << 24);
  // Unsigned right-shift to convert signed 32-bit to unsigned
  return (ptr >>> 0) - GBA_ROM_BASE;
}

// ── Battle-music string table ──────────────────────────────────────────────
//
// Unbound stores battle-BGM identifiers in a pointer table at 0x1FB30E8.
// Each entry is a 4-byte GBA pointer to a null-terminated CFRU string.
// After the FR build the strings must be French (they were relocated to
// free space because the FR forms are slightly longer than the EN originals).
//
// Table indices (0-based, stride 4):
//   43 → "Combat ! Ho-Oh"   (pointer at 0x1FB3194)
//   44 → "Combat ! Lugia"   (pointer at 0x1FB3198)
//
const BATTLE_BGM_TABLE = 0x1fb30e8;

const BATTLE_BGM_CHECKS: Array<{ name: string; entry: number; expect: string }> = [
  { name: 'Ho-Oh', entry: 43, expect: 'Combat ! Ho-Oh' },
  { name: 'Lugia', entry: 44, expect: 'Combat ! Lugia' },
];

test.describe('Rencontre Ho-Oh / Lugia — intégrité ROM', () => {
  test('les chaînes de musique de combat sont en français et terminées', () => {
    const rom = fs.readFileSync(ROM_PATH);

    for (const { name, entry, expect: needle } of BATTLE_BGM_CHECKS) {
      const ptrOffset = BATTLE_BGM_TABLE + entry * 4;
      const strOffset = readPointer(rom, ptrOffset);

      expect(
        strOffset,
        `pointeur de table pour ${name} hors de la plage ROM`,
      ).toBeGreaterThan(0);
      expect(strOffset).toBeLessThan(rom.length);

      const { text, terminated } = readRomString(rom, strOffset);
      expect(
        terminated,
        `0x${strOffset.toString(16)}: "Combat ! ${name}" sans terminateur 0xFF`,
      ).toBe(true);
      expect(
        text,
        `0x${strOffset.toString(16)}: attendu "${needle}" — reçu "${text}"`,
      ).toBe(needle);
    }
  });

  // ── NPC dialogue strings in the Ho-Oh encounter area (0x7Bxxxx) ──────────
  //
  // These strings are either applied in-place (shorter FR fits in EN slot) or
  // relocated to free space (pointer updated). In either case the FR ROM must
  // contain French text, properly terminated.
  //
  // Inline strings (FR ≤ EN, no pointer change):
  //   0x7B1CE1 — "J'ai entendu …"
  //   0x7B1D45 — "As-tu vu …"
  //   0x7B1D65 — "Hmm, je continue …"
  //
  // Relocated strings (FR > EN, pointer at listed address updated):
  //   ptr @ 0x7A8D7F → "Apparemment, l'oiseau …"   (was 0x7B1D1E)
  //   ptr @ 0x7AA2BC → "C'est dans ces moments …"  (was 0x7B1D97)
  //
  const INLINE_STRINGS: Array<{ offset: number; needle: string }> = [
    { offset: 0x7b1ce1, needle: 'entendu' },
    { offset: 0x7b1d45, needle: 'Pok' },
    { offset: 0x7b1d65, needle: 'continue' },
  ];

  const RELOCATED_PTRS: Array<{ ptrOffset: number; needle: string }> = [
    { ptrOffset: 0x7a8d7f, needle: 'oiseau' },
    { ptrOffset: 0x7aa2bc, needle: 'moments' },
  ];

  test('les dialogues PNJ de la zone de Ho-Oh sont en français et terminés', () => {
    const rom = fs.readFileSync(ROM_PATH);

    for (const { offset, needle } of INLINE_STRINGS) {
      const { text, terminated } = readRomString(rom, offset);
      expect(
        terminated,
        `0x${offset.toString(16)}: dialogue PNJ sans terminateur 0xFF`,
      ).toBe(true);
      expect(
        text,
        `0x${offset.toString(16)}: texte français attendu contenant "${needle}"`,
      ).toContain(needle);
      // Must not start with an English word that crept back in
      expect(text).not.toMatch(/^[A-Z][a-z]+ the /);
    }

    for (const { ptrOffset, needle } of RELOCATED_PTRS) {
      const strOffset = readPointer(rom, ptrOffset);
      expect(strOffset).toBeGreaterThan(0);
      expect(strOffset).toBeLessThan(rom.length);

      const { text, terminated } = readRomString(rom, strOffset);
      expect(
        terminated,
        `ptr@0x${ptrOffset.toString(16)}→0x${strOffset.toString(16)}: sans terminateur 0xFF`,
      ).toBe(true);
      expect(
        text,
        `ptr@0x${ptrOffset.toString(16)}: texte français attendu contenant "${needle}"`,
      ).toContain(needle);
    }
  });

  // ── Rainbow Wing item ─────────────────────────────────────────────────────
  //
  // Item table base: 0x876074, stride 44 bytes.
  // Item 0x298 = Rainbow Wing.  Name field is the first 14 bytes of each
  // item entry (13 glyphs max + 0xFF terminator).
  // Description pointer at name_base + 0x14.
  //
  // The Silver Wing (0x299) is at the next entry; verifying it stays correct
  // guards against off-by-one in the patch.
  //
  const ITEM_TABLE_BASE = 0x876074;
  const ITEM_STRIDE = 44;
  const ITEM_DESC_PTR_OFFSET = 0x14;

  const ITEM_CHECKS: Array<{
    index: number;
    name: string;
    expectedName: string;
    descNeedle: string;
  }> = [
    {
      index: 0x298,
      name: 'Rainbow Wing',
      expectedName: 'Aile Aurore',
      descNeedle: 'arc-en-ciel',
    },
    {
      index: 0x299,
      name: 'Silver Wing',
      expectedName: 'Aile Argent',
      descNeedle: 'argent',
    },
  ];

  test('les noms et descriptions des objets Aile Aurore / Aile Argentée sont en français', () => {
    const rom = fs.readFileSync(ROM_PATH);

    for (const { index, name, expectedName, descNeedle } of ITEM_CHECKS) {
      const itemBase = ITEM_TABLE_BASE + index * ITEM_STRIDE;

      // Name field (up to 13 glyphs + 0xFF)
      const { text: itemName, terminated: nameTerminated } = readRomString(
        rom,
        itemBase,
        14,
      );
      expect(
        nameTerminated,
        `item ${name}: nom sans terminateur`,
      ).toBe(true);
      expect(
        itemName,
        `item ${name}: attendu contenir "${expectedName}"`,
      ).toContain(expectedName);

      // Description (via pointer at +0x14)
      const descPtrOff = itemBase + ITEM_DESC_PTR_OFFSET;
      const descOffset = readPointer(rom, descPtrOff);
      expect(descOffset).toBeGreaterThan(0);
      expect(descOffset).toBeLessThan(rom.length);

      const { text: desc, terminated: descTerminated } = readRomString(
        rom,
        descOffset,
      );
      expect(
        descTerminated,
        `item ${name}: description sans terminateur`,
      ).toBe(true);
      expect(
        desc,
        `item ${name}: description française attendue contenant "${descNeedle}"`,
      ).toContain(descNeedle);
    }
  });
});
