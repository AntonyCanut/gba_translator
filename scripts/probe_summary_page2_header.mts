/**
 * probe_summary_page2_header.mts — Dump the Pokémon Summary screen's
 * page-2 (Skills) AND page-3 (Moves) header banners, for offline tile
 * analysis (B-228 split ticket: DE page-2 header wrongly reads
 * "Pokemon-Attacken" instead of "Fähigkeiten").
 *
 * Reuses the same savestate-driven navigation as probe_hp_vram.mts (party →
 * context menu → summary), then pages RIGHT twice to also capture the Moves
 * page header, so the two banners' tiles can be diffed to check whether the
 * page-2 header shares the exact same tile block as the (correctly-labelled)
 * Moves page banner.
 *
 * Run:  npx tsx scripts/probe_summary_page2_header.mts <fr|de>
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const LANG = process.argv[2] ?? 'fr';
const ROM = path.resolve(`output/roms/GenedRom-${LANG}.gba`);
const OUT_DIR = path.resolve('output/proofs/summary-header');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, `${LANG}-${name}.png`));
    console.error(`[shot] ${LANG}-${name}`);
  } catch (e) {
    console.error(`[shot] ${LANG}-${name} failed: ${String(e)}`);
  }
}

async function dumpRegion(
  client: MgbaBridgeClient,
  base: number,
  size: number,
  file: string,
): Promise<void> {
  const chunks: Uint8Array[] = [];
  for (let off = 0; off < size; off += 4096) {
    const len = Math.min(4096, size - off);
    chunks.push(await client.readMemory(base + off, len));
  }
  const buf = Buffer.concat(chunks.map((c) => Buffer.from(c)));
  fs.writeFileSync(path.join(OUT_DIR, file), buf);
  console.error(`[dump] ${file}: ${buf.length} bytes from 0x${base.toString(16)}`);
}

async function dumpScreen(client: MgbaBridgeClient, tag: string): Promise<void> {
  await dumpRegion(client, 0x06000000, 0x10000, `${LANG}-${tag}-vram-bg.bin`);
  await dumpRegion(client, 0x06010000, 0x8000, `${LANG}-${tag}-vram-obj.bin`);
  await dumpRegion(client, 0x05000000, 0x400, `${LANG}-${tag}-pal.bin`);
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${ROM}`);
  await client.startMgba(ROM);

  await client.advanceFrames(600);
  await client.loadState(2);
  await client.advanceFrames(30);

  for (let i = 0; i < 3; i++) {
    await client.pressKey('B', 4);
    await client.advanceFrames(20);
  }
  await client.pressKey('START', 4);
  await client.advanceFrames(40);
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await client.pressKey('A', 4);
  await client.advanceFrames(30);
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await shot(client, '01-info');
  await dumpScreen(client, '01-info');

  await client.pressKey('RIGHT', 4);
  await client.advanceFrames(60);
  await shot(client, '02-skills');
  await dumpScreen(client, '02-skills');

  await client.pressKey('RIGHT', 4);
  await client.advanceFrames(60);
  await shot(client, '03-moves');
  await dumpScreen(client, '03-moves');

  await client.stop();
  console.error('[probe] done');
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
