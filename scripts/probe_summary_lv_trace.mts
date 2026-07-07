/**
 * probe_summary_lv_trace.mts — Execution-trace the Summary "Info" page
 * (team list → A → A) to locate the font/mechanism rendering the "Lv10"
 * header next to the Pokémon icon (B-236).
 *
 * F-114 established that this header is NOT the party-list ligature glyph
 * (codepoint 0x05 @ 0x1ECFA0): patching that glyph has no visible effect on
 * this screen (verified empirically). This probe re-runs F-113's
 * width-table read-watch strategy (probe_party_lv_trace.mts) but opens the
 * Summary Info page instead of the party list, to see which font (if any)
 * renders "Lv10" here via a normal width-table lookup.
 *
 * Run:  MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_summary_lv_trace.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import { MgbaBridgeClient, type WatchHit } from '../emulator-web/src/mgba-bridge.js';

const ROM_BASE = 0x08000000;
const DEFAULT_ROM = 'output/roms/GenedRom-fr.gba';
const DEFAULT_SS2 = 'output/roms/GenedRom-fr.ss2';

const WIDTH_TABLES: Array<{ name: string; off: number }> = [
  { name: 'small@1E9F00', off: 0x1e9f00 },
  { name: 'small@1EA100', off: 0x1ea100 },
  { name: 'small@1EA200', off: 0x1ea200 },
  { name: 'small@1EA600', off: 0x1ea600 },
  { name: 'small@1EAF00', off: 0x1eaf00 },
  { name: 'small@1EEF00', off: 0x1eef00 },
  { name: 'small@1EF100', off: 0x1ef100 },
  { name: 'font@1FB100', off: 0x1fb100 },
  { name: 'font@207300', off: 0x207300 },
  { name: 'font@217618', off: 0x217618 },
  { name: 'font@227930', off: 0x227930 },
];
const WIDTH_TABLE_LEN = 0x100;

const ROM = path.resolve(process.argv[2] ?? DEFAULT_ROM);

function ensureSavestate(): void {
  const want = ROM.replace(/\.gba$/i, '.ss2');
  const src = path.resolve(DEFAULT_SS2);
  if (path.resolve(want) !== src) {
    if (!fs.existsSync(src)) throw new Error(`savestate not found: ${src}`);
    fs.copyFileSync(src, want);
    console.error(`[trace] copied savestate -> ${want}`);
  }
}

function romPointers(regs: Record<string, number>): string {
  return Object.entries(regs)
    .filter(([, v]) => v >= ROM_BASE && v < 0x0a000000)
    .map(([k, v]) => `${k}=0x${(v >>> 0).toString(16)}`)
    .join(' ') || '(none)';
}

function summarise(hits: WatchHit[]): void {
  const groups = new Map<string, { count: number; sample: WatchHit }>();
  for (const h of hits) {
    const pc = h.regs.r15 ?? 0;
    const key = `${h.label}|pc=${(pc >>> 0).toString(16)}`;
    const g = groups.get(key);
    if (g) g.count++;
    else groups.set(key, { count: 1, sample: h });
  }
  const rows = [...groups.entries()].sort((a, b) => b[1].count - a[1].count);
  console.error(`\n[trace] ${hits.length} width-table read hits, ${rows.length} distinct read sites:`);
  for (const [key, { count, sample }] of rows) {
    const lr = sample.regs.r14 ?? 0;
    console.error(`  ${count.toString().padStart(4)}×  ${key}  lr=0x${(lr >>> 0).toString(16)}`);
    console.error(`         glyphId=r0=0x${(sample.regs.r0 >>> 0).toString(16)} readAddr=0x${sample.addr.toString(16)} romRegs: ${romPointers(sample.regs)}`);
  }
  if (rows.length === 0) {
    console.error('  (no width-table reads captured — Summary Info page does not use these fonts)');
  }
}

async function main(): Promise<void> {
  ensureSavestate();
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.loadState(2);
  await c.advanceFrames(30);

  const caps = await c.capabilities();
  console.error('[trace] mGBA debugger caps:', JSON.stringify(caps));
  if (!caps.setRangeWatchpoint && !caps.setWatchpoint) {
    throw new Error('this mGBA build has no scripting watchpoints (need >= 0.11)');
  }

  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }

  const ids: number[] = [];
  for (const t of WIDTH_TABLES) {
    const min = ROM_BASE + t.off;
    const id = await c.setRangeWatchpoint(min, min + WIDTH_TABLE_LEN, 'R');
    ids.push(id);
    console.error(`[trace] armed READ watch ${t.name} [0x${min.toString(16)},+0x${WIDTH_TABLE_LEN.toString(16)}) id=${id}`);
  }

  // Navigate to the Summary Info page BEFORE arming (clear hits), then clear
  // hits and re-open (close+reopen) so only the Info-page render is captured.
  await c.pressKey('START', 4); await c.advanceFrames(40);
  await c.pressKey('A', 4); await c.advanceFrames(90);
  await c.pressKey('A', 4); await c.advanceFrames(30);

  await c.clearWatchHits();
  await c.pressKey('A', 4); await c.advanceFrames(90);

  const shot = ROM.replace(/\.gba$/i, '') + '.summary_lv_trace.png';
  await c.screenshot(shot);
  console.error(`[trace] screenshot -> ${shot}`);

  const hits = await c.drainWatchHits();
  for (const id of ids) { try { await c.clearBreakpoint(id); } catch { /* ignore */ } }

  summarise(hits);

  const out = ROM.replace(/\.gba$/i, '') + '.summary_lv_trace.json';
  fs.writeFileSync(out, JSON.stringify(hits, null, 2));
  console.error(`[trace] full hit dump -> ${out}`);

  await c.stop();
}

main().catch((e) => { console.error('[trace] FATAL', e); process.exit(1); });
