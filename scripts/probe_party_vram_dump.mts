/**
 * probe_party_vram_dump.mts — Open the party (START → Pokémon) screen and dump
 * VRAM + BG registers + palettes to disk, so the exact on-screen « Lv » graphic
 * tile can be located and then matched back to its LZ77 source in the ROM.
 *
 * The execution trace (probe_party_lv_trace.mts) proved the party screen's
 * « Lv » is NOT text (no font renders it) — it is a baked graphic like « PV ».
 * This dump lets us find which VRAM tile shows it.
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_party_vram_dump.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const DEFAULT_ROM = 'output/roms/GenedRom-fr.gba';
const DEFAULT_SS2 = 'output/roms/GenedRom-fr.ss2';
const ROM = path.resolve(process.argv[2] ?? DEFAULT_ROM);

function ensureSavestate(): void {
  const want = ROM.replace(/\.gba$/i, '.ss2');
  const src = path.resolve(DEFAULT_SS2);
  if (path.resolve(want) !== src) {
    if (!fs.existsSync(src)) throw new Error(`savestate not found: ${src}`);
    fs.copyFileSync(src, want);
  }
}

async function dump(c: MgbaBridgeClient, addr: number, len: number): Promise<Buffer> {
  const out = Buffer.alloc(len);
  const CHUNK = 4096;
  for (let o = 0; o < len; o += CHUNK) {
    const n = Math.min(CHUNK, len - o);
    const bytes = await c.readMemory(addr + o, n);
    out.set(bytes, o);
  }
  return out;
}

async function main(): Promise<void> {
  ensureSavestate();
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.loadState(2);
  await c.advanceFrames(30);
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }
  await c.pressKey('START', 4); await c.advanceFrames(60);
  await c.pressKey('A', 4); await c.advanceFrames(220);

  const base = ROM.replace(/\.gba$/i, '');
  await c.screenshot(base + '.party_vram.png');

  const vram = await dump(c, 0x06000000, 0x18000);     // 96 KB VRAM
  fs.writeFileSync(base + '.vram.bin', vram);
  const pal = await dump(c, 0x05000000, 0x400);        // 1 KB palette RAM
  fs.writeFileSync(base + '.pal.bin', pal);
  // DISPCNT + BG0-3 CNT + BG scroll/offsets (0x04000000..0x04000020)
  const io = await dump(c, 0x04000000, 0x60);
  fs.writeFileSync(base + '.io.bin', io);
  console.error(`[vram] dumped VRAM(0x18000) pal(0x400) io(0x60) next to ${base}`);

  await c.stop();
}

main().catch((e) => { console.error('[vram] FATAL', e); process.exit(1); });
