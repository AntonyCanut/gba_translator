/**
 * probe_party_lv_source.mts — Trace who WRITES the « Lv » pixels into VRAM on the
 * party screen (issue #48 / B-234 / F-113). The font trace proved no glyph font
 * renders « Lv », so it is drawn by some raw blit / tileset copy. We arm a WRITE
 * watchpoint over the exact BG0 char tiles that hold « Lv » (tx1-2, ty3-4 =
 * VRAM char tiles 0x8D/0x8E/0x9B/0x9C at charbase 0) and capture the writing
 * code (r15/r14) plus the source pointer registers.
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_party_lv_source.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import { MgbaBridgeClient, type WatchHit } from '../emulator-web/src/mgba-bridge.js';

const DEFAULT_ROM = 'output/roms/GenedRom-fr.gba';
const DEFAULT_SS2 = 'output/roms/GenedRom-fr.ss2';
const ROM = path.resolve(process.argv[2] ?? DEFAULT_ROM);

// Step-2 watch: the EWRAM window tile buffer that feeds the « Lv » VRAM tiles
// (VRAM copy source was r3=0x2001c88). Whoever blits « Lv » here from a ROM
// graphic is the source we want. Env WATCH_MIN/WATCH_MAX override for iterating.
const VRAM_MIN = parseInt(process.env.WATCH_MIN ?? '0x02001c00', 16);
const VRAM_MAX = parseInt(process.env.WATCH_MAX ?? '0x02001e00', 16); // exclusive

function ensureSavestate(): void {
  const want = ROM.replace(/\.gba$/i, '.ss2');
  const src = path.resolve(DEFAULT_SS2);
  if (path.resolve(want) !== src) {
    if (!fs.existsSync(src)) throw new Error(`savestate not found: ${src}`);
    fs.copyFileSync(src, want);
  }
}

function rp(regs: Record<string, number>): string {
  return Object.entries(regs)
    .filter(([, v]) => (v >= 0x08000000 && v < 0x0a000000) || (v >= 0x02000000 && v < 0x03008000))
    .map(([k, v]) => `${k}=0x${(v >>> 0).toString(16)}`)
    .join(' ') || '(none)';
}

async function main(): Promise<void> {
  ensureSavestate();
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.loadState(2);
  await c.advanceFrames(30);
  const caps = await c.capabilities();
  console.error('[src] caps', JSON.stringify(caps));

  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }
  const id = await c.setRangeWatchpoint(VRAM_MIN, VRAM_MAX, 'W');
  console.error(`[src] armed WRITE watch [0x${VRAM_MIN.toString(16)},0x${VRAM_MAX.toString(16)}) id=${id}`);
  await c.clearWatchHits();

  await c.pressKey('START', 4); await c.advanceFrames(60);
  await c.pressKey('A', 4); await c.advanceFrames(220);

  const hits: WatchHit[] = await c.drainWatchHits();
  try { await c.clearBreakpoint(id); } catch { /* ignore */ }

  // Histogram by writing PC.
  const groups = new Map<string, { count: number; sample: WatchHit }>();
  for (const h of hits) {
    const key = `pc=${(h.regs.r15 >>> 0).toString(16)} lr=${(h.regs.r14 >>> 0).toString(16)}`;
    const g = groups.get(key);
    if (g) g.count++; else groups.set(key, { count: 1, sample: h });
  }
  console.error(`\n[src] ${hits.length} VRAM writes to the « Lv » tiles, ${groups.size} distinct writers:`);
  for (const [key, { count, sample }] of [...groups].sort((a, b) => b[1].count - a[1].count)) {
    console.error(`  ${count.toString().padStart(4)}×  ${key}`);
    console.error(`         wroteAddr=0x${sample.addr.toString(16)} new=0x${(sample.new>>>0).toString(16)} ptrRegs: ${rp(sample.regs)}`);
  }
  const out = ROM.replace(/\.gba$/i, '') + '.party_lv_source.json';
  fs.writeFileSync(out, JSON.stringify(hits, null, 2));
  console.error(`[src] dump -> ${out}`);
  await c.stop();
}

main().catch((e) => { console.error('[src] FATAL', e); process.exit(1); });
