/**
 * probe_naming_sprites.mts — Locate the "Cancel" (ANNUL.) and "Selection"
 * (SELECT/RET./BOUTON B/OK/START/MAJ./min./autres) keyboard-panel graphics
 * by dumping VRAM while the player-naming keyboard screen is displayed
 * (ticket F-109, follow-up of F-108).
 *
 * Boots the FR ROM fresh (New Game), walks the intro to the player naming
 * keyboard screen, screenshots + dumps BG/OBJ VRAM and palettes.
 *
 * Run:  npx tsx scripts/probe_naming_sprites.mts [rom]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/naming-vram');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, `${name}.png`));
    console.error(`[shot] ${name}`);
  } catch (e) {
    console.error(`[shot] ${name} failed: ${String(e)}`);
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
  await dumpRegion(client, 0x06000000, 0x10000, `${tag}-vram-bg.bin`);
  await dumpRegion(client, 0x06010000, 0x8000, `${tag}-vram-obj.bin`);
  await dumpRegion(client, 0x05000000, 0x400, `${tag}-pal.bin`);
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${ROM}`);
  await client.startMgba(ROM);

  await client.advanceFrames(600);
  await shot(client, '01-title');

  // New Game
  await client.pressKey('START', 4);
  await client.advanceFrames(60);
  await shot(client, '02-titlemenu');
  await client.pressKey('A', 4);
  await client.advanceFrames(120);
  await shot(client, '03-newgame-start');

  // Mash through Birch intro dialogue/character-customization screens; the
  // naming keyboard reliably appears around i=15-20 (calibrated via a prior
  // screenshot sweep).
  for (let i = 0; i < 18; i++) {
    await client.pressKey('A', 4);
    await client.advanceFrames(60);
  }
  await shot(client, '10-keyboard');
  await dumpScreen(client, 'keyboard');
  await client.saveState(5);
  console.error('[probe] saved keyboard-screen state to slot 5');

  // Cycle the shift/symbols tab (SELECT key) to see the "others"/"MAJ"/"min"
  // placeholder states referenced by the Selection.bmp reference art.
  await client.pressKey('SELECT', 4);
  await client.advanceFrames(30);
  await shot(client, '11-keyboard-select1');
  await dumpScreen(client, 'keyboard-select1');
  await client.pressKey('SELECT', 4);
  await client.advanceFrames(30);
  await shot(client, '12-keyboard-select2');
  await dumpScreen(client, 'keyboard-select2');

  // Back out with B to see if a Cancel confirmation/graphic appears.
  await client.pressKey('B', 4);
  await client.advanceFrames(40);
  await shot(client, '13-after-b');
  await dumpScreen(client, 'after-b');
  await client.pressKey('B', 4);
  await client.advanceFrames(40);
  await shot(client, '14-after-b2');
  await dumpScreen(client, 'after-b2');

  await client.stop();
  console.error('[probe] done — inspect screenshots under', OUT_DIR);
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
