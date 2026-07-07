/**
 * probe_party_lv_blit.mts — Breakpoint the generic window bitmap-blit function
 * (0x08004AA4) during party-screen draw and capture its source-pointer args, to
 * find the « Lv » bitmap source (issue #48 / B-234 / F-113).
 *
 * The font trace proved « Lv » is not a width-table font glyph; the VRAM/EWRAM
 * write traces showed « Lv » pixels are plotted by this blit function. A blit
 * whose source register points into cart ROM (0x08.. /0x09..) — as opposed to a
 * RAM glyph-staging buffer — is a baked bitmap, i.e. the « Lv » graphic.
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_party_lv_blit.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import { MgbaBridgeClient, type WatchHit } from '../emulator-web/src/mgba-bridge.js';

const DEFAULT_ROM = 'output/roms/GenedRom-fr.gba';
const DEFAULT_SS2 = 'output/roms/GenedRom-fr.ss2';
const ROM = path.resolve(process.argv[2] ?? DEFAULT_ROM);
const BLIT_FN = parseInt(process.env.BP ?? '0x08004aa4', 16);

function ensureSavestate(): void {
  const want = ROM.replace(/\.gba$/i, '.ss2');
  const src = path.resolve(DEFAULT_SS2);
  if (path.resolve(want) !== src) {
    if (!fs.existsSync(src)) throw new Error(`savestate not found: ${src}`);
    fs.copyFileSync(src, want);
  }
}

async function main(): Promise<void> {
  ensureSavestate();
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.loadState(2);
  await c.advanceFrames(30);
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }

  const id = await c.setBreakpoint(BLIT_FN);
  console.error(`[blit] breakpoint at 0x${BLIT_FN.toString(16)} id=${id}`);
  await c.clearWatchHits();

  await c.pressKey('START', 4); await c.advanceFrames(60);
  await c.pressKey('A', 4); await c.advanceFrames(220);

  const hits: WatchHit[] = await c.drainWatchHits();
  try { await c.clearBreakpoint(id); } catch { /* ignore */ }

  console.error(`\n[blit] ${hits.length} calls to 0x${BLIT_FN.toString(16)}. Calls with a ROM-range source arg:`);
  let romCalls = 0;
  for (let i = 0; i < hits.length; i++) {
    const r = hits[i].regs;
    const romArgs = ['r0', 'r1', 'r2', 'r3'].filter(k => r[k] >= 0x08000000 && r[k] < 0x0a000000);
    if (romArgs.length) {
      romCalls++;
      if (romCalls <= 40) {
        const shown = ['r0', 'r1', 'r2', 'r3', 'r4', 'r5'].map(k => `${k}=0x${(r[k] >>> 0).toString(16)}`).join(' ');
        console.error(`  #${i}: ${shown}`);
      }
    }
  }
  console.error(`[blit] ${romCalls}/${hits.length} calls had a ROM source arg`);
  const out = ROM.replace(/\.gba$/i, '') + '.party_lv_blit.json';
  fs.writeFileSync(out, JSON.stringify(hits, null, 2));
  console.error(`[blit] dump -> ${out}`);
  await c.stop();
}

main().catch((e) => { console.error('[blit] FATAL', e); process.exit(1); });
