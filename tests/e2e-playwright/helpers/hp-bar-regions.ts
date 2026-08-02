import fs from 'fs';
import { PNG } from 'pngjs';

/** A rectangle in GBA framebuffer coordinates (240×160). */
export interface Region {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const SCREEN_WIDTH = 240;
export const SCREEN_HEIGHT = 160;

export const FULL_SCREEN_REGION: Region = {
  x: 0, y: 0, width: SCREEN_WIDTH, height: SCREEN_HEIGHT,
};

/**
 * The two stat labels of the « Pokémon Skills » page that stay byte-identical
 * in every build, used together as a language-independent way to recognise the
 * page. They are deliberately disjoint from {@link HP_BAR_REGION}: the screen
 * is identified by pixels that the fix under test cannot influence.
 *
 * The label column is six capsules on a 12-pixel pitch from y 38 — ATTACK,
 * DEFENSE, SP.ATK, SP.DEF, SPEED, EXP. All six are word-image tiles that the
 * *text* pipeline leaves untouched, so the whole column used to be a single
 * anchor. GitHub issue #145 ended that: `languages/fr/patches/
 * summary_stat_labels.py` now redraws four of them in French (ATTAQUE,
 * ATT SPE., DEF SPE., VITESSE) and the hand-drawn sheet keeps them. Only
 * DEFENSE — transparent in French — and EXP. are still shared.
 *
 * Each band is exactly the 9 rows of its capsule, nothing more: a capsule's
 * top and bottom rows hug its word, so a band one row too tall reaches into
 * the neighbouring French capsule and the page stops being recognised.
 */
export const STAT_CAPSULE_HEIGHT = 9;

export const PAGE_ANCHOR_REGIONS: Region[] = [
  { x: 0, y: 50, width: 56, height: STAT_CAPSULE_HEIGHT },  // DEFENSE
  { x: 0, y: 98, width: 56, height: STAT_CAPSULE_HEIGHT },  // EXP.
];

/**
 * Screen coordinates of the bar, for the record: the label sprite covers
 * x 66-81 (its last column, x 81, is the bar's left cap), the six body tiles
 * x 82-129 and the right-cap tile starts at x 130. The region below adds a
 * one-pixel margin on every side so a bar drawn too tall — the Spanish
 * 7-row body — also shows up as a difference.
 */

/**
 * The HP bar of the same page, without the « HP » / « PV » label letters that
 * legitimately differ between languages. Both bar end caps are inside it:
 * GitHub issue #84 is exactly those caps missing from the French build.
 */
export const HP_BAR_REGION: Region = { x: 81, y: 29, width: 51, height: 7 };

/**
 * The « HP » / « PV » / « KP » / « PS » letters left of the same bar, stopping
 * one pixel before the bar's left cap at x 81.
 *
 * The parity assertions deliberately exclude these letters, which leaves a
 * hole: a build that shipped the *English* sheet wholesale — bar intact, label
 * untranslated — would satisfy every parity check. Requiring this region to
 * differ from the English capture closes it.
 */
export const HP_LABEL_REGION: Region = { x: 66, y: 29, width: 15, height: 7 };

/**
 * The six HP bars of the party menu, one per slot (left column then right,
 * top to bottom). Same rule: caps included, « HP » / « PV » letters excluded.
 *
 * The rest of the party screen cannot be compared across builds — the species
 * names are translated and the Pokémon icons animate, so a full-screen golden
 * of that page is both language-specific and unstable from one run to the next.
 * These six bands are pure BG tiles and hold still.
 */
export const PARTY_HP_BAR_REGIONS: Region[] = [
  { x: 62, y: 20, width: 52, height: 7 },
  { x: 174, y: 30, width: 52, height: 7 },
  { x: 62, y: 62, width: 52, height: 7 },
  { x: 174, y: 68, width: 52, height: 7 },
  { x: 62, y: 100, width: 52, height: 7 },
  { x: 174, y: 108, width: 52, height: 7 },
];

/**
 * Where the probe drops its party-menu capture, next to the Skills-page one.
 * It lives here rather than in the probe so the spec can import it without
 * loading the probe's entry point.
 */
export function partyScreenshotPath(screenshotPath: string): string {
  return screenshotPath.replace(/\.png$/, '.party.png');
}

export function readScreen(filePath: string): PNG {
  const png = PNG.sync.read(fs.readFileSync(filePath));
  if (png.width !== SCREEN_WIDTH || png.height !== SCREEN_HEIGHT) {
    throw new Error(
      `capture ${filePath} is ${png.width}×${png.height}, expected ${SCREEN_WIDTH}×${SCREEN_HEIGHT}`,
    );
  }
  return png;
}

/** Decode a standalone region reference (already cropped) into RGBA pixels. */
export function readRegionReference(filePath: string, region: Region): Buffer {
  const png = PNG.sync.read(fs.readFileSync(filePath));
  if (png.width !== region.width || png.height !== region.height) {
    throw new Error(
      `reference ${filePath} is ${png.width}×${png.height}, expected `
      + `${region.width}×${region.height}`,
    );
  }
  return Buffer.from(png.data);
}

/**
 * Decode a multi-band reference — the bands of {@link PAGE_ANCHOR_REGIONS}
 * stacked top to bottom in one image, in the order they are declared.
 */
export function readAnchorReference(filePath: string, regions: Region[]): Buffer {
  const width = regions[0].width;
  const height = regions.reduce((total, region) => total + region.height, 0);
  if (regions.some((region) => region.width !== width)) {
    throw new Error('anchor bands must all share the same width');
  }
  return readRegionReference(filePath, { x: 0, y: 0, width, height });
}

export function cropRegion(png: PNG, region: Region): Buffer {
  const out = Buffer.alloc(region.width * region.height * 4);
  for (let row = 0; row < region.height; row++) {
    const src = ((region.y + row) * png.width + region.x) * 4;
    png.data.copy(out, row * region.width * 4, src, src + region.width * 4);
  }
  return out;
}

export function regionsMatch(a: PNG, b: PNG, region: Region): boolean {
  return cropRegion(a, region).equals(cropRegion(b, region));
}

/** Crop several bands and stack them, in declaration order, into one buffer. */
export function cropRegions(png: PNG, regions: Region[]): Buffer {
  return Buffer.concat(regions.map((region) => cropRegion(png, region)));
}

/** True when *a* and *b* agree on every band of *regions*. */
export function regionsMatchAll(a: PNG, b: PNG, regions: Region[]): boolean {
  return cropRegions(a, regions).equals(cropRegions(b, regions));
}

/** Number of pixels that differ inside *region* — used in failure messages. */
export function regionDiffCount(a: PNG, b: PNG, region: Region): number {
  const left = cropRegion(a, region);
  const right = cropRegion(b, region);
  let diff = 0;
  for (let i = 0; i < left.length; i += 4) {
    if (left.readUInt32BE(i) !== right.readUInt32BE(i)) {
      diff++;
    }
  }
  return diff;
}

/**
 * How many distinct colours *region* holds.
 *
 * A pixel-parity test between two captures passes trivially when both are
 * blank — a black screen equals a black screen. Counting colours proves the
 * probe really captured a drawn bar before any parity claim is made.
 */
export function distinctColours(png: PNG, region: Region): number {
  const colours = new Set<number>();
  for (let row = 0; row < region.height; row++) {
    for (let col = 0; col < region.width; col++) {
      const at = ((region.y + row) * png.width + region.x + col) * 4;
      colours.add(png.data.readUInt32BE(at));
    }
  }
  return colours.size;
}

/** Fraction of the framebuffer that changed between two captures. */
export function screenDiffRatio(a: PNG, b: PNG): number {
  return regionDiffCount(a, b, FULL_SCREEN_REGION) / (SCREEN_WIDTH * SCREEN_HEIGHT);
}

/** Render a region as an ASCII map of colour ids, for readable diffs. */
export function describeRegion(png: PNG, region: Region): string {
  const palette = new Map<number, string>();
  const glyphs = '.123456789abcdefghijklmnopqrstuvwxyz';
  const lines: string[] = [];
  for (let row = 0; row < region.height; row++) {
    let line = '';
    for (let col = 0; col < region.width; col++) {
      const at = ((region.y + row) * png.width + region.x + col) * 4;
      const rgb = png.data.readUInt32BE(at);
      if (!palette.has(rgb)) {
        palette.set(rgb, glyphs[Math.min(palette.size, glyphs.length - 1)]);
      }
      line += palette.get(rgb);
    }
    lines.push(line);
  }
  return lines.join('\n');
}
