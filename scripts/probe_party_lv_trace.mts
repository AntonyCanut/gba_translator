/**
 * probe_party_lv_trace.mts — Execution-trace the party (START → Pokémon) screen
 * to locate the uncompressed FRLG font that renders the « Lv » level prefix
 * (issue #48 / B-234 / F-113 follow-up).
 *
 * Strategy: the FRLG text engine reads a per-font *glyph-width table* once for
 * every glyph it lays out. Four uncompressed-font width tables are known
 * (font.py:WIDTH_TABLE_OFFSETS). We arm a READ range-watchpoint over each table,
 * open the party list, then drain the captured hits. Whichever table is read
 * while the party screen draws identifies the font the screen actually uses —
 * and each hit carries the full ARM register file (r15 = PC of the read,
 * r14 = LR of the caller), which pins the GetGlyphWidth / glyph-blit code so the
 * glyph-tile table address can be recovered from there.
 *
 * Requires mGBA >= 0.11 (scripting watchpoints). See docs/analysis/
 * party_menu_lv_investigation.md for the full context.
 *
 * Run:  MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_party_lv_trace.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import { MgbaBridgeClient, type WatchHit } from '../emulator-web/src/mgba-bridge.js';

const ROM_BASE = 0x08000000;
const DEFAULT_ROM = 'output/roms/GenedRom-fr.gba';
const DEFAULT_SS2 = 'output/roms/GenedRom-fr.ss2';

// Candidate uncompressed-font glyph-width tables. The four in
// font.py:WIDTH_TABLE_OFFSETS plus the smaller-font family discovered by
// literal-pool scan (glyph_base + 0x8000 = width_table, stride 0x40/glyph).
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
const WIDTH_TABLE_LEN = 0x100; // one width byte per codepoint (0..255)

const ROM = path.resolve(process.argv[2] ?? DEFAULT_ROM);

function ensureSavestate(): void {
  // loadStateSlot(2) reads "<rom-basename>.ss2"; copy the overworld savestate
  // next to a patched/alternate ROM or the game boots cold (blank screen).
  const want = ROM.replace(/\.gba$/i, '.ss2');
  const src = path.resolve(DEFAULT_SS2);
  if (path.resolve(want) !== src) {
    if (!fs.existsSync(src)) throw new Error(`savestate not found: ${src}`);
    fs.copyFileSync(src, want);
    console.error(`[trace] copied savestate -> ${want}`);
  }
}

function romPointers(regs: Record<string, number>): string {
  // Registers pointing into cart ROM (0x08.../0x09...) — candidate font/struct ptrs.
  return Object.entries(regs)
    .filter(([, v]) => v >= ROM_BASE && v < 0x0a000000)
    .map(([k, v]) => `${k}=0x${(v >>> 0).toString(16)}`)
    .join(' ') || '(none)';
}

function summarise(hits: WatchHit[]): void {
  // Group by (table label, PC) so the recurring read site stands out.
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
    console.error('  (no width-table reads captured — party screen does not use these fonts)');
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

  // Close any open UI, arm the width-table read-watchpoints, then open the menu.
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }

  const ids: number[] = [];
  for (const t of WIDTH_TABLES) {
    const min = ROM_BASE + t.off;
    const id = await c.setRangeWatchpoint(min, min + WIDTH_TABLE_LEN, 'R');
    ids.push(id);
    console.error(`[trace] armed READ watch ${t.name} [0x${min.toString(16)},+0x${WIDTH_TABLE_LEN.toString(16)}) id=${id}`);
  }
  await c.clearWatchHits();

  await c.pressKey('START', 4); await c.advanceFrames(60);
  await c.pressKey('A', 4); await c.advanceFrames(220);
  // Move the cursor between party slots — forces the box (nickname + Lv + HP)
  // text to be redrawn, which is exactly the « Lv » render we want to catch.
  await c.pressKey('DOWN', 4); await c.advanceFrames(40);
  await c.pressKey('DOWN', 4); await c.advanceFrames(40);
  await c.pressKey('UP', 4); await c.advanceFrames(40);

  const shot = ROM.replace(/\.gba$/i, '') + '.party_lv_trace.png';
  await c.screenshot(shot);
  console.error(`[trace] screenshot -> ${shot}`);

  const hits = await c.drainWatchHits();
  for (const id of ids) { try { await c.clearBreakpoint(id); } catch { /* ignore */ } }

  summarise(hits);

  // Emit a machine-readable dump for follow-up disassembly.
  const out = ROM.replace(/\.gba$/i, '') + '.party_lv_trace.json';
  fs.writeFileSync(out, JSON.stringify(hits, null, 2));
  console.error(`[trace] full hit dump -> ${out}`);

  await c.stop();
}

main().catch((e) => { console.error('[trace] FATAL', e); process.exit(1); });
