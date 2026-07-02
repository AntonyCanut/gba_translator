/**
 * probe_hp_vram.mts — Locate the party-menu "HP" and summary-screen "PS"
 * label tiles by dumping VRAM while the screens are displayed.
 *
 * Boots the FR ROM, restores savestate slot 2 (in-game save with Pokémon),
 * navigates START menu → Pokémon (party screen) then Résumé (summary screen),
 * screenshotting each step and dumping BG VRAM + palettes to binary files for
 * offline tile analysis.
 *
 * Run:  npx tsx scripts/probe_hp_vram.mts [step]
 *   step=menu    only reach the START menu (navigation calibration)
 *   step=full    party + summary VRAM dumps (default)
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve('output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/hp-vram');
fs.mkdirSync(OUT_DIR, { recursive: true });

const STEP = process.argv[2] ?? 'full';

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
  // Full BG VRAM (4 charblocks + screenblocks) + OBJ charblocks + palettes
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

  // Restore in-game savestate (slot 2 = output/roms/GenedRom-fr.ss2)
  await client.loadState(2);
  await client.advanceFrames(30);
  await shot(client, '02-state');

  // Close any open UI, then open START menu
  for (let i = 0; i < 3; i++) {
    await client.pressKey('B', 4);
    await client.advanceFrames(20);
  }
  await shot(client, '03-idle');
  await client.pressKey('START', 4);
  await client.advanceFrames(40);
  await shot(client, '04-startmenu');

  if (STEP === 'menu') {
    await client.stop();
    return;
  }

  // Unbound uses an icon-bar START menu; the default selection is already
  // "Pokémon" (calibrated via 04-startmenu screenshot) — just confirm.
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await shot(client, '06-party');
  await dumpScreen(client, 'party');
  if (STEP === 'ram') {
    // Work RAM dumps to trace runtime-composited graphics back to their source
    await dumpRegion(client, 0x02000000, 0x40000, 'party-ewram.bin');
    await dumpRegion(client, 0x03000000, 0x8000, 'party-iwram.bin');
    await client.stop();
    return;
  }

  // Open summary of first mon: A → context menu → Résumé (first entry) → A
  await client.pressKey('A', 4);
  await client.advanceFrames(30);
  await shot(client, '07-party-context');
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await shot(client, '08-summary');
  await dumpScreen(client, 'summary');

  // Page right once (stats page shows the grey HP label + green bar label)
  await client.pressKey('RIGHT', 4);
  await client.advanceFrames(60);
  await shot(client, '09-summary-skills');
  await dumpScreen(client, 'summary-skills');

  await client.stop();
  console.error('[probe] done');
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
