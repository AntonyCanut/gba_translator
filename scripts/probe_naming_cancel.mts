/**
 * probe_naming_cancel.mts — Continue the Unbound intro flashback (loaded
 * from savestate slot 5) by walking DOWN through the ship corridor, mixing
 * in A presses for dialogue, trying to reach the starter-Pokémon / nickname
 * screen where a graphical CANCEL button is expected (ticket F-109).
 *
 * Does not yet reach that screen — the flashback corridor still blocks
 * progress after 60 walk batches (see saved slot 6, and
 * output/proofs/naming-vram/50-down-*.png). Left as a starting point for
 * continuing the Cancel-button search; see the F-109 follow-up ticket.
 *
 * Run: npx tsx scripts/probe_naming_cancel.mts [rom]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/naming-vram');

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, name));
  } catch (e) {
    console.error(`[shot] ${name} failed: ${String(e)}`);
  }
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error('[probe] booting');
  await client.startMgba(ROM);
  await client.advanceFrames(10);
  await client.loadState(5);
  await client.advanceFrames(30);
  await client.pressKey('START', 4);
  await client.advanceFrames(60);
  for (let i = 0; i < 300; i++) {
    await client.pressKey('A', 4);
    await client.advanceFrames(50);
  }
  console.error('[probe] flashback dialogue mashed, now walking');

  for (let batch = 0; batch < 60; batch++) {
    for (let i = 0; i < 3; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(30);
    }
    for (let s = 0; s < 8; s++) {
      await client.pressKey('DOWN', 4);
      await client.advanceFrames(14);
    }
    if (batch % 5 === 0) {
      await shot(client, `50-down-${String(batch).padStart(3, '0')}.png`);
    }
  }
  await shot(client, '51-final.png');
  await client.saveState(6);
  console.error('[probe] saved slot 6, done');
  await client.stop();
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
