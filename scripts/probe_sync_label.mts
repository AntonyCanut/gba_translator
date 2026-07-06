/**
 * probe_sync_label.mts — Synchronized screenshot+OAM+OBJ-VRAM capture at the
 * naming keyboard screen (slot 5) and after one SELECT press, to resolve
 * whether the shift-state pill label (others/UPPER/lower) lives in a fixed
 * OBJ tile slot whose VRAM bytes get rewritten, or moves to a different tile
 * id (ticket F-109).
 *
 * Run: npx tsx scripts/probe_sync_label.mts [rom]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/naming-vram');

async function readChunked(client: MgbaBridgeClient, base: number, size: number): Promise<Buffer> {
  const chunks: Uint8Array[] = [];
  for (let off = 0; off < size; off += 4096) {
    const len = Math.min(4096, size - off);
    chunks.push(await client.readMemory(base + off, len));
  }
  return Buffer.concat(chunks.map((c) => Buffer.from(c)));
}

async function capture(client: MgbaBridgeClient, tag: string): Promise<void> {
  await client.screenshot(path.join(OUT_DIR, `${tag}.png`));
  const oam = await readChunked(client, 0x07000000, 0x400);
  fs.writeFileSync(path.join(OUT_DIR, `${tag}-oam.bin`), oam);
  const obj = await readChunked(client, 0x06010000, 0x8000);
  fs.writeFileSync(path.join(OUT_DIR, `${tag}-vram-obj.bin`), obj);
  console.error(`[capture] ${tag} done`);
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  await client.startMgba(ROM);
  await client.advanceFrames(10);
  await client.loadState(5);
  await client.advanceFrames(20);
  await capture(client, 'sync-base');

  await client.pressKey('SELECT', 4);
  await client.advanceFrames(40);
  await capture(client, 'sync-select1');

  await client.pressKey('SELECT', 4);
  await client.advanceFrames(40);
  await capture(client, 'sync-select2');

  await client.stop();
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
